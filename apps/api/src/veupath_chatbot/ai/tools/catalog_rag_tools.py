"""AI tools for Qdrant-backed catalog retrieval."""

from __future__ import annotations

from typing import cast

from veupath_chatbot.integrations.embeddings.openai_embeddings import embed_one
from veupath_chatbot.integrations.vectorstore.bootstrap import ensure_rag_collections
from veupath_chatbot.integrations.vectorstore.collections import (
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
from veupath_chatbot.platform.config import get_settings
from veupath_chatbot.platform.types import JSONArray, JSONObject, JSONValue


class CatalogRagTools:
    """RAG-first tools for exploring VEuPathDB catalog.

    These tools read from Qdrant and fall back to authoritative WDK calls only for
    context-dependent vocab (dependent params) via the cached pathway.


    """

    def __init__(self, *, site_id: str) -> None:
        self.site_id = site_id
        self._store = QdrantStore.from_settings()

    async def rag_get_record_types(
        self,
        query: str | None = None,
        limit: int = 20,
        min_score: float = 0.40,
    ) -> JSONArray:
        settings = get_settings()
        if not settings.rag_enabled:
            return []
        await ensure_rag_collections()
        q = (query or "").strip()
        if not q:
            # No query: return empty and let caller use live get_record_types if desired.
            return []
        vec = await embed_one(text=q, model=settings.embeddings_model)
        hits = await self._store.search(
            collection=WDK_RECORD_TYPES_V1,
            query_vector=vec,
            # Over-fetch a bit so the score threshold doesn't return an empty list too often.
            limit=max(int(limit) * 3, int(limit), 1),
            must=cast(JSONArray, [{"key": "siteId", "value": self.site_id}]),
        )
        out: JSONArray = []
        threshold = float(min_score)
        for h_value in hits:
            if not isinstance(h_value, dict):
                continue
            h = h_value
            score_raw = h.get("score")
            score = float(
                score_raw if isinstance(score_raw, (int, float, str)) else 0.0
            )
            if score < threshold:
                continue
            payload_raw = h.get("payload")
            payload = payload_raw if isinstance(payload_raw, dict) else None
            if not isinstance(payload, dict):
                continue
            # Keep record-type discovery payloads small for the UI:
            # these WDK schema-ish fields can be massive and are often irrelevant at this stage.
            pruned = dict(payload)
            pruned.pop("formats", None)
            pruned.pop("attributes", None)
            pruned.pop("tables", None)
            out.append({"score": score, **pruned})
            if len(out) >= int(limit):
                break
        return out

    async def rag_get_record_type_details(
        self,
        record_type_id: str,
    ) -> JSONObject | None:
        """Retrieve one record type payload from Qdrant by id."""
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

    async def rag_search_for_searches(
        self,
        query: str,
        record_type: str | None = None,
        limit: int = 20,
        min_score: float = 0.40,
    ) -> JSONArray:
        settings = get_settings()
        if not settings.rag_enabled:
            return []
        await ensure_rag_collections()
        q = (query or "").strip()
        if not q:
            return []
        vec = await embed_one(text=q, model=settings.embeddings_model)
        must: JSONArray = [cast(JSONValue, {"key": "siteId", "value": self.site_id})]
        if record_type:
            must.append(cast(JSONValue, {"key": "recordType", "value": record_type}))
        hits = await self._store.search(
            collection=WDK_SEARCHES_V1,
            query_vector=vec,
            # Over-fetch a bit so the score threshold doesn't return an empty list too often.
            limit=max(int(limit) * 3, int(limit), 1),
            must=must,
        )
        out: JSONArray = []
        threshold = float(min_score)
        for h_value in hits:
            if not isinstance(h_value, dict):
                continue
            h = h_value
            score_raw = h.get("score")
            score = float(
                score_raw if isinstance(score_raw, (int, float, str)) else 0.0
            )
            if score < threshold:
                continue
            payload_raw = h.get("payload")
            payload = payload_raw if isinstance(payload_raw, dict) else None
            if not isinstance(payload, dict):
                continue
            # Keep search discovery payloads small for the UI:
            # these schema-ish fields can be massive and are often irrelevant at this stage.
            pruned = dict(payload)
            pruned.pop("score", None)
            pruned.pop("format", None)
            pruned.pop("dynamicAttributes", None)
            pruned.pop("paramSpecs", None)
            out.append({"score": score, **pruned})
            if len(out) >= int(limit):
                break
        return out

    async def rag_get_search_metadata(
        self,
        record_type: str,
        search_name: str,
    ) -> JSONObject | None:
        settings = get_settings()
        if not settings.rag_enabled:
            return None
        pid = point_uuid(f"{self.site_id}:{record_type}:{search_name}")
        hit = await self._store.get(collection=WDK_SEARCHES_V1, point_id=pid)
        if not hit:
            return None
        payload_raw = hit.get("payload")
        return payload_raw if isinstance(payload_raw, dict) else None

    async def rag_get_dependent_vocab(
        self,
        record_type: str,
        search_name: str,
        param_name: str,
        context_values: JSONObject | None = None,
    ) -> JSONObject:
        settings = get_settings()
        if not settings.rag_enabled:
            return {"error": "rag_disabled"}
        return await get_dependent_vocab_authoritative_cached(
            site_id=self.site_id,
            record_type=record_type,
            search_name=search_name,
            param_name=param_name,
            context_values=context_values or {},
            store=self._store,
        )
