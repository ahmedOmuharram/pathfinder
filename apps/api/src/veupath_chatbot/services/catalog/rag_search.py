"""RAG search service: embed -> query Qdrant -> threshold -> prune.

Centralises the shared pattern used by catalog and example-plan RAG tools
so that the AI tool layer never touches integrations directly.
"""

from collections.abc import Sequence
from typing import cast

from veupath_chatbot.domain.search import SearchContext
from veupath_chatbot.integrations.embeddings.openai_embeddings import embed_one
from veupath_chatbot.integrations.vectorstore.bootstrap import ensure_rag_collections
from veupath_chatbot.integrations.vectorstore.collections import (
    EXAMPLE_PLANS_V1,
    WDK_RECORD_TYPES_V1,
    WDK_SEARCHES_V1,
)
from veupath_chatbot.integrations.vectorstore.dependent_vocab_cache import (
    get_dependent_vocab_authoritative_cached,
)
from veupath_chatbot.integrations.vectorstore.qdrant_store import (
    QdrantStore,
    point_uuid,
)
from veupath_chatbot.integrations.veupathdb.discovery import (
    get_discovery_service,
)
from veupath_chatbot.integrations.veupathdb.wdk_models import WDKSearchResponse
from veupath_chatbot.platform.config import get_settings
from veupath_chatbot.platform.types import (
    JSONArray,
    JSONObject,
    JSONValue,
    as_json_object,
)

# ── helpers ──────────────────────────────────────────────────────────


def _extract_score(hit: JSONObject) -> float:
    """Extract numeric score from a Qdrant hit dict."""
    score_raw = hit.get("score")
    return float(score_raw if isinstance(score_raw, (int, float, str)) else 0.0)


def _extract_payload(hit: JSONObject) -> JSONObject | None:
    """Extract payload dict from a Qdrant hit dict."""
    payload_raw = hit.get("payload")
    return payload_raw if isinstance(payload_raw, dict) else None


def _threshold_and_limit(
    hits: JSONArray,
    *,
    min_score: float,
    limit: int,
    prune_keys: Sequence[str] = (),
) -> JSONArray:
    """Filter hits by score, prune payload keys, and cap at *limit*."""
    out: JSONArray = []
    for h_value in hits:
        if not isinstance(h_value, dict):
            continue
        score = _extract_score(h_value)
        if score < min_score:
            continue
        payload = _extract_payload(h_value)
        if payload is None:
            continue
        pruned = dict(payload)
        for key in prune_keys:
            pruned.pop(key, None)
        out.append({"score": score, **pruned})
        if len(out) >= limit:
            break
    return out


# ── public API ───────────────────────────────────────────────────────


class RagSearchService:
    """Stateless service encapsulating all Qdrant-backed lookups.

    Constructed with a *site_id*; owns its own ``QdrantStore`` instance.
    """

    def __init__(self, *, site_id: str, store: QdrantStore | None = None) -> None:
        self.site_id = site_id
        self._store = store or QdrantStore.from_settings()

    # ── record types ─────────────────────────────────────────────────

    async def search_record_types(
        self,
        query: str | None = None,
        limit: int = 20,
        min_score: float = 0.40,
    ) -> JSONArray:
        """Semantic search over WDK record types."""
        settings = get_settings()
        if not settings.rag_enabled:
            return []
        await ensure_rag_collections()
        q = (query or "").strip()
        if not q:
            return []
        vec = await embed_one(text=q, model=settings.embeddings_model)
        hits = await self._store.search(
            collection=WDK_RECORD_TYPES_V1,
            query_vector=vec,
            limit=max(int(limit) * 3, int(limit), 1),
            must=cast("JSONArray", [{"key": "siteId", "value": self.site_id}]),
        )
        return _threshold_and_limit(
            hits,
            min_score=float(min_score),
            limit=int(limit),
            prune_keys=("formats", "attributes", "tables"),
        )

    async def get_record_type_details(
        self,
        record_type_id: str,
    ) -> JSONObject | None:
        """Retrieve one record-type payload from Qdrant by id."""
        settings = get_settings()
        if not settings.rag_enabled:
            return None
        rt = str(record_type_id or "").strip()
        if not rt:
            return None
        pid = point_uuid(f"{self.site_id}:{rt}")
        hit = await self._store.get(collection=WDK_RECORD_TYPES_V1, point_id=pid)
        if not hit:
            return None
        payload_raw = hit.get("payload")
        return payload_raw if isinstance(payload_raw, dict) else None

    # ── searches ─────────────────────────────────────────────────────

    async def search_for_searches(
        self,
        query: str,
        record_type: str | None = None,
        limit: int = 20,
        min_score: float = 0.40,
    ) -> JSONArray:
        """Semantic search over WDK searches."""
        settings = get_settings()
        if not settings.rag_enabled:
            return []
        await ensure_rag_collections()
        q = (query or "").strip()
        if not q:
            return []
        vec = await embed_one(text=q, model=settings.embeddings_model)
        must: JSONArray = [cast("JSONValue", {"key": "siteId", "value": self.site_id})]
        if record_type:
            must.append(cast("JSONValue", {"key": "recordType", "value": record_type}))
        hits = await self._store.search(
            collection=WDK_SEARCHES_V1,
            query_vector=vec,
            limit=max(int(limit) * 3, int(limit), 1),
            must=must,
        )
        return _threshold_and_limit(
            hits,
            min_score=float(min_score),
            limit=int(limit),
            prune_keys=("score", "format", "dynamicAttributes", "paramSpecs"),
        )

    async def get_search_metadata(
        self,
        record_type: str,
        search_name: str,
    ) -> JSONObject | None:
        """Retrieve one search payload from Qdrant by composite key."""
        settings = get_settings()
        if not settings.rag_enabled:
            return None
        pid = point_uuid(f"{self.site_id}:{record_type}:{search_name}")
        hit = await self._store.get(collection=WDK_SEARCHES_V1, point_id=pid)
        if not hit:
            return None
        payload_raw = hit.get("payload")
        return payload_raw if isinstance(payload_raw, dict) else None

    # ── dependent vocab ──────────────────────────────────────────────

    async def get_dependent_vocab(
        self,
        record_type: str,
        search_name: str,
        param_name: str,
        context_values: JSONObject | None = None,
    ) -> JSONObject:
        """Fetch dependent vocab (Qdrant-cached, WDK fallback on miss)."""
        settings = get_settings()
        if not settings.rag_enabled:
            return {"error": "rag_disabled"}
        return await get_dependent_vocab_authoritative_cached(
            SearchContext(self.site_id, record_type, search_name),
            param_name=param_name,
            context_values=context_values or {},
            store=self._store,
        )

    # ── example plans ────────────────────────────────────────────────

    async def search_example_plans(
        self,
        query: str,
        limit: int = 5,
    ) -> JSONArray:
        """Semantic search over ingested public strategies."""
        settings = get_settings()
        if not settings.rag_enabled:
            return []
        await ensure_rag_collections()
        q = (query or "").strip()
        if not q:
            return []
        vec = await embed_one(text=q, model=settings.embeddings_model)
        hits = await self._store.search(
            collection=EXAMPLE_PLANS_V1,
            query_vector=vec,
            limit=limit,
            must=[{"key": "siteId", "value": self.site_id}],
        )
        out: JSONArray = []
        for h_value in hits:
            if not isinstance(h_value, dict):
                continue
            h = as_json_object(h_value)
            payload_value = h.get("payload")
            if not isinstance(payload_value, dict):
                payload_value = {}
            p = as_json_object(payload_value)
            strategy_full = p.get("strategyFull")
            strategy_compact_value = p.get("strategyCompact")
            strategy_compact: JSONObject = {}
            if isinstance(strategy_compact_value, dict):
                strategy_compact = strategy_compact_value
            out.append(
                {
                    "score": h.get("score"),
                    "sourceSignature": p.get("sourceSignature"),
                    "sourceStrategyId": p.get("sourceStrategyId"),
                    "sourceName": p.get("sourceName"),
                    "sourceDescription": p.get("sourceDescription"),
                    "generatedName": p.get("generatedName"),
                    "generatedDescription": p.get("generatedDescription"),
                    "recordClassName": p.get("recordClassName"),
                    "rootStepId": p.get("rootStepId"),
                    "strategyCompact": strategy_compact,
                    "strategyFull": strategy_full,
                }
            )
        return out

    # ── search details fallback (wraps DiscoveryService) ─────────────

    async def get_search_details(
        self,
        record_type: str,
        search_name: str,
        *,
        expand_params: bool = True,
    ) -> WDKSearchResponse:
        """Proxy to DiscoveryService.get_search_details for dependent-vocab fallbacks."""
        discovery = get_discovery_service()
        return await discovery.get_search_details(
            SearchContext(self.site_id, record_type, search_name),
            expand_params=expand_params,
        )
