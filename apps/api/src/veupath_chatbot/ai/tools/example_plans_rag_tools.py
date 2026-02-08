"""AI tools for retrieving example plans from Qdrant."""

from __future__ import annotations

from typing import Any

from veupath_chatbot.platform.config import get_settings
from veupath_chatbot.services.embeddings.openai_embeddings import embed_one
from veupath_chatbot.services.vectorstore.collections import EXAMPLE_PLANS_V1
from veupath_chatbot.services.vectorstore.qdrant_store import QdrantStore


class ExamplePlansRagTools:
    def __init__(self, *, site_id: str) -> None:
        self.site_id = site_id
        self._store = QdrantStore.from_settings()

    async def rag_search_example_plans(
        self,
        query: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        settings = get_settings()
        if not settings.rag_enabled:
            return []
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
        out: list[dict[str, Any]] = []
        for h in hits:
            p = h.get("payload") or {}
            strategy_full = p.get("strategyFull") if isinstance(p, dict) else None
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
                    "strategyCompact": (p.get("strategyCompact") or {}),
                    "strategyFull": strategy_full,
                }
            )
        return out

