"""Shared research tool mixin (web + literature search).

Used by both `PlannerToolRegistryMixin` and `AgentToolRegistryMixin` so that
web and literature search are available regardless of conversation mode.
"""

from typing import Annotated, cast

from kani import AIParam, ai_function
from pydantic import BaseModel, Field

from veupath_chatbot.domain.research import (
    LiteratureFilters,
    LiteratureOutputOptions,
    LiteratureSort,
)
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.research import (
    LiteratureSearchService,
    WebSearchService,
)


class LiteratureSearchFilters(BaseModel):
    """Optional filters applied to literature search results."""

    year_from: int | None = Field(
        default=None,
        description="Optional inclusive minimum publication year",
    )
    year_to: int | None = Field(
        default=None,
        description="Optional inclusive maximum publication year",
    )
    author_includes: str | None = Field(
        default=None,
        description="Optional substring filter against author names",
    )
    title_includes: str | None = Field(
        default=None,
        description="Optional substring filter against titles",
    )
    journal_includes: str | None = Field(
        default=None,
        description="Optional substring filter against journal name",
    )
    doi_equals: str | None = Field(
        default=None,
        description="Optional DOI exact match filter",
    )
    pmid_equals: str | None = Field(
        default=None,
        description="Optional PMID exact match filter (Europe PMC only)",
    )
    require_doi: bool = Field(
        default=False,
        description="If true, only return results that include a DOI",
    )


class LiteratureSearchOutputOptions(BaseModel):
    """Output formatting options for literature search."""

    include_abstract: bool = Field(
        default=True,
        description=(
            "If true, include abstracts/summaries when available "
            "(may require extra fetches)."
        ),
    )
    abstract_max_chars: int = Field(
        default=2000,
        description="Max characters of abstract/summary to include per result.",
    )
    max_authors: int = Field(
        default=2,
        description=(
            "Max authors to keep per result/citation (default 2). "
            "Use -1 to include all authors. When truncated, remaining authors are "
            "replaced by 'et al.'. Don't modify this parameter unless you're sure "
            "you need to."
        ),
    )


_DEFAULT_OUTPUT_OPTIONS = LiteratureSearchOutputOptions()
_DEFAULT_FILTERS = LiteratureSearchFilters()


class ResearchToolsMixin:
    """Mixin that exposes web and literature search as Kani tools.

    Classes using this mixin must provide these attributes:

    - web_search_service: WebSearchService
    - literature_search_service: LiteratureSearchService
    """

    web_search_service: WebSearchService = cast(
        "WebSearchService", cast("object", None)
    )
    literature_search_service: LiteratureSearchService = cast(
        "LiteratureSearchService", cast("object", None)
    )

    @ai_function()
    async def web_search(
        self,
        query: Annotated[str, AIParam(desc="Web search query")],
        limit: Annotated[int, AIParam(desc="Max number of results (1-10)")] = 5,
        *,
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
        return await search_method(
            query,
            limit=limit,
            include_summary=include_summary,
            summary_max_chars=summary_max_chars,
        )

    @ai_function()
    async def literature_search(
        self,
        query: Annotated[str, AIParam(desc="Literature search query")],
        limit: Annotated[int, AIParam(desc="Max number of results (1-25)")] = 8,
        sort: Annotated[
            LiteratureSort, AIParam(desc="Sort order: relevance (default) or newest")
        ] = "relevance",
        *,
        output_options: LiteratureSearchOutputOptions = _DEFAULT_OUTPUT_OPTIONS,
        filters: LiteratureSearchFilters = _DEFAULT_FILTERS,
    ) -> JSONObject:
        """Search scientific literature across all sources and return results with citations."""
        search_method = self.literature_search_service.search
        return await search_method(
            query,
            source="all",
            limit=limit,
            sort=sort,
            options=LiteratureOutputOptions(
                include_abstract=output_options.include_abstract,
                abstract_max_chars=output_options.abstract_max_chars,
                max_authors=output_options.max_authors,
            ),
            filters=LiteratureFilters(
                year_from=filters.year_from,
                year_to=filters.year_to,
                author_includes=filters.author_includes,
                title_includes=filters.title_includes,
                journal_includes=filters.journal_includes,
                doi_equals=filters.doi_equals,
                pmid_equals=filters.pmid_equals,
                require_doi=filters.require_doi,
            ),
        )
