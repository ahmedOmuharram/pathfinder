"""AI tools for retrieving example plans from Qdrant."""

from __future__ import annotations

from veupath_chatbot.integrations.embeddings.openai_embeddings import embed_one
from veupath_chatbot.integrations.vectorstore.bootstrap import ensure_rag_collections
from veupath_chatbot.integrations.vectorstore.collections import EXAMPLE_PLANS_V1
from veupath_chatbot.integrations.vectorstore.qdrant_store import QdrantStore
from veupath_chatbot.platform.config import get_settings
from veupath_chatbot.platform.types import JSONArray, JSONObject


class ExamplePlansRagTools:
    def __init__(self, *, site_id: str) -> None:
        self.site_id = site_id
        self._store = QdrantStore.from_settings()

    async def rag_search_example_plans(
        self,
        query: str,
        limit: int = 5,
    ) -> JSONArray:
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
        # Return full payloads so the model can directly inspect the original name/description
        # and the full stepTree/steps for each example.
        from veupath_chatbot.platform.types import as_json_object

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
            # Keep the most relevant fields at the top-level to reduce nesting.
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
