"""Research clients that answer nothing, for turns run against the mock model."""

from __future__ import annotations

from pathfinder.domain.research.citations import (
    LiteratureFilters,
    LiteratureOutputOptions,
    LiteratureSort,
    LiteratureSource,
)
from pathfinder.services.research.literature_search import LiteratureSearchService
from pathfinder.services.research.processing import LiteratureSearchResponse
from pathfinder.services.research.web_search import (
    SearchDiagnostics,
    WebSearchResponse,
    WebSearchService,
)


class StubLiteratureSearchService(LiteratureSearchService):
    async def search(
        self,
        query: str,
        *,
        source: LiteratureSource = "all",
        limit: int = 5,
        sort: LiteratureSort = "relevance",
        options: LiteratureOutputOptions | None = None,
        filters: LiteratureFilters | None = None,
    ) -> LiteratureSearchResponse:
        del limit, options
        return LiteratureSearchResponse(
            query=query,
            source=source,
            sort=sort,
            include_abstract=False,
            abstract_max_chars=500,
            max_authors=2,
            filters=filters or LiteratureFilters(),
            results=[],
            citations=[],
        )


class StubWebSearchService(WebSearchService):
    async def search(
        self,
        query: str,
        limit: int = 5,
        *,
        include_summary: bool = False,
        summary_max_chars: int = 600,
    ) -> WebSearchResponse:
        del limit, include_summary, summary_max_chars
        return WebSearchResponse(
            query=query,
            effective_query=query,
            search_adjusted=False,
            search_diagnostics=SearchDiagnostics(),
            results=[],
            citations=[],
        )


__all__ = ["StubLiteratureSearchService", "StubWebSearchService"]
