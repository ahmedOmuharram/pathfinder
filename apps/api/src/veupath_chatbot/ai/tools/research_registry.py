"""Shared research tool mixin (web + literature search).

Used by both `PlannerToolRegistryMixin` and `AgentToolRegistryMixin` so that
web and literature search are available regardless of conversation mode.
"""

from __future__ import annotations

from typing import Annotated

from kani import AIParam, ai_function

from veupath_chatbot.domain.research import LiteratureSort
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.research import (
    LiteratureSearchService,
    WebSearchService,
)


class ResearchToolsMixin:
    """Mixin that exposes web and literature search as Kani tools.

    Classes using this mixin must provide these attributes:
    - web_search_service: WebSearchService
    - literature_search_service: LiteratureSearchService
    """

    web_search_service: WebSearchService
    literature_search_service: LiteratureSearchService

    @ai_function()
    async def web_search(
        self,
        query: Annotated[str, AIParam(desc="Web search query")],
        limit: Annotated[int, AIParam(desc="Max number of results (1-10)")] = 5,
        include_summary: Annotated[
            bool,
            AIParam(
                desc=(
                    "If true, fetch each result page (best-effort) to extract a short "
                    "summary/description when snippets are unhelpful."
                )
            ),
        ] = True,
        summary_max_chars: Annotated[
            int, AIParam(desc="Max characters of per-result summary to include.")
        ] = 600,
    ) -> JSONObject:
        """Search the web and return results with citations."""
        search_method = self.web_search_service.search
        result = await search_method(
            query,
            limit=limit,
            include_summary=include_summary,
            summary_max_chars=summary_max_chars,
        )
        return result

    @ai_function()
    async def literature_search(
        self,
        query: Annotated[str, AIParam(desc="Literature search query")],
        limit: Annotated[int, AIParam(desc="Max number of results (1-25)")] = 8,
        sort: Annotated[
            LiteratureSort, AIParam(desc="Sort order: relevance (default) or newest")
        ] = "relevance",
        max_authors: Annotated[
            int,
            AIParam(
                desc=(
                    "Max authors to keep per result/citation (default 2). "
                    "Use -1 to include all authors. When truncated, remaining authors are replaced by 'et al.'. "
                    "Don't modify this parameter unless you're sure you need to."
                )
            ),
        ] = 2,
        include_abstract: Annotated[
            bool,
            AIParam(
                desc=(
                    "If true, include abstracts/summaries when available (may require extra fetches)."
                )
            ),
        ] = True,
        abstract_max_chars: Annotated[
            int,
            AIParam(desc="Max characters of abstract/summary to include per result."),
        ] = 2000,
        year_from: Annotated[
            int | None, AIParam(desc="Optional inclusive minimum publication year")
        ] = None,
        year_to: Annotated[
            int | None, AIParam(desc="Optional inclusive maximum publication year")
        ] = None,
        author_includes: Annotated[
            str | None, AIParam(desc="Optional substring filter against author names")
        ] = None,
        title_includes: Annotated[
            str | None, AIParam(desc="Optional substring filter against titles")
        ] = None,
        journal_includes: Annotated[
            str | None, AIParam(desc="Optional substring filter against journal name")
        ] = None,
        doi_equals: Annotated[
            str | None, AIParam(desc="Optional DOI exact match filter")
        ] = None,
        pmid_equals: Annotated[
            str | None,
            AIParam(desc="Optional PMID exact match filter (Europe PMC only)"),
        ] = None,
        require_doi: Annotated[
            bool, AIParam(desc="If true, only return results that include a DOI")
        ] = False,
    ) -> JSONObject:
        """Search scientific literature across all sources and return results with citations."""
        search_method = self.literature_search_service.search
        result = await search_method(
            query,
            source="all",
            limit=limit,
            sort=sort,
            max_authors=max_authors,
            include_abstract=include_abstract,
            abstract_max_chars=abstract_max_chars,
            year_from=year_from,
            year_to=year_to,
            author_includes=author_includes,
            title_includes=title_includes,
            journal_includes=journal_includes,
            doi_equals=doi_equals,
            pmid_equals=pmid_equals,
            require_doi=require_doi,
        )
        return result
