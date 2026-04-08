"""Standalone research tools (web + literature search) for pydantic-ai migration."""

from pydantic_ai import RunContext

from pathfinder.ai.orchestration.deps import AgentDeps
from pathfinder.ai.tools.standalone._research_models import (
    _DEFAULT_FILTERS,
    _DEFAULT_OUTPUT_OPTIONS,
    LiteratureSearchFilters,
    LiteratureSearchOutputOptions,
)
from pathfinder.domain.research import (
    LiteratureFilters,
    LiteratureOutputOptions,
    LiteratureSort,
)
from pathfinder.services.research.processing import LiteratureSearchResponse
from pathfinder.services.research.web_search import WebSearchResponse


async def web_search(
    ctx: RunContext[AgentDeps],
    query: str,
    limit: int = 5,
    include_summary: bool = True,
    summary_max_chars: int = 600,
) -> WebSearchResponse:
    """Search the web and return results with citations.

    Args:
        ctx: Agent run context.
        query: Web search query.
        limit: Max number of results (1-10).
        include_summary: If true, fetch each result page (best-effort) to extract
            a short summary/description when snippets are unhelpful.
        summary_max_chars: Max characters of per-result summary to include.
    """
    service = ctx.deps.web_search_service
    if service is None:
        msg = "web_search_service is not configured"
        raise RuntimeError(msg)
    return await service.search(
        query,
        limit=limit,
        include_summary=include_summary,
        summary_max_chars=summary_max_chars,
    )


async def literature_search(
    ctx: RunContext[AgentDeps],
    query: str,
    limit: int = 8,
    sort: LiteratureSort = "relevance",
    output_options: LiteratureSearchOutputOptions = _DEFAULT_OUTPUT_OPTIONS,
    filters: LiteratureSearchFilters = _DEFAULT_FILTERS,
) -> LiteratureSearchResponse:
    """Search scientific literature across all sources and return results with citations.

    Args:
        ctx: Agent run context.
        query: Literature search query.
        limit: Max number of results (1-25).
        sort: Sort order: relevance (default) or newest.
        output_options: Output formatting options.
        filters: Optional filters applied to results.
    """
    service = ctx.deps.literature_search_service
    if service is None:
        msg = "literature_search_service is not configured"
        raise RuntimeError(msg)
    return await service.search(
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
