"""AI tools for Qdrant-backed catalog retrieval.

Thin delegation layer — all logic lives in ``services.catalog.rag_search``.
"""

from veupath_chatbot.platform.types import JSONArray, JSONObject
from veupath_chatbot.services.catalog.rag_search import RagSearchService


class CatalogRagTools:
    """RAG-first tools for exploring VEuPathDB catalog.

    These tools read from Qdrant and fall back to authoritative WDK calls only for
    context-dependent vocab (dependent params) via the cached pathway.

    When ``disabled=True`` all methods return empty results, allowing RAG
    ablation experiments without removing tool registrations.
    """

    def __init__(self, *, site_id: str, disabled: bool = False) -> None:
        self.site_id = site_id
        self._disabled = disabled
        self._svc = RagSearchService(site_id=site_id)

    async def rag_get_record_types(
        self,
        query: str | None = None,
        limit: int = 20,
        min_score: float = 0.40,
    ) -> JSONArray:
        if self._disabled:
            return []
        return await self._svc.search_record_types(
            query=query, limit=limit, min_score=min_score
        )

    async def rag_get_record_type_details(
        self,
        record_type_id: str,
    ) -> JSONObject | None:
        if self._disabled:
            return None
        return await self._svc.get_record_type_details(record_type_id)

    async def rag_search_for_searches(
        self,
        query: str,
        record_type: str | None = None,
        limit: int = 20,
        min_score: float = 0.40,
    ) -> JSONArray:
        if self._disabled:
            return []
        return await self._svc.search_for_searches(
            query=query,
            record_type=record_type,
            limit=limit,
            min_score=min_score,
        )

    async def rag_get_search_metadata(
        self,
        record_type: str,
        search_name: str,
    ) -> JSONObject | None:
        if self._disabled:
            return None
        return await self._svc.get_search_metadata(record_type, search_name)

    async def rag_get_dependent_vocab(
        self,
        record_type: str,
        search_name: str,
        param_name: str,
        context_values: JSONObject | None = None,
    ) -> JSONObject:
        if self._disabled:
            return {}
        return await self._svc.get_dependent_vocab(
            record_type,
            search_name,
            param_name,
            context_values,
        )
