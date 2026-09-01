"""Web and literature search, capped to what the model reads.

A search answers with a ranked index. The leading results carry their text;
the rest carry the identity that reaches the full record again.
"""

from __future__ import annotations

from assistant_core.graph.tool_summary import with_summary
from pydantic_ai import RunContext
from pydantic_ai.messages import ToolReturn

from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.tools.standalone._research_models import (
    _DEFAULT_FILTERS,
    _DEFAULT_OUTPUT_OPTIONS,
    LiteratureSearchFilters,
    LiteratureSearchOut,
    LiteratureSearchOutputOptions,
    PaperOut,
    WebResultOut,
    WebSearchOut,
)
from pathfinder.ai.tools.standalone._stream_parts import (
    source_url_chunks_from_citations,
)
from pathfinder.domain.research import (
    LiteratureFilters,
    LiteratureOutputOptions,
    LiteratureSort,
)
from pathfinder.services.research.processing import (
    EnrichedPaper,
    LiteratureSearchResponse,
)
from pathfinder.services.research.utils import truncate_text
from pathfinder.services.research.web_search import WebSearchResponse, WebSearchResult

# A claim is grounded on the leading results, which keep their text. The rest
# are an index: enough to judge, and enough to ask for again.
LEADING_RESULTS = 3
LEADING_CHARS = 600
INDEXED_CHARS = 200

_WEB_GUIDANCE = (
    "Ranked most relevant first. Only the first "
    f"{LEADING_RESULTS} carry the page text; the rest carry the url that "
    "holds it."
)
_LITERATURE_GUIDANCE = (
    "Ranked most relevant first. Only the first "
    f"{LEADING_RESULTS} carry the abstract. For a paper further down, call "
    "literature_search again with its title or its DOI and limit 1."
)


def _text_at(rank: int, *values: str | None) -> str:
    """The first value with text in it, cut to what this rank is worth."""
    limit = LEADING_CHARS if rank < LEADING_RESULTS else INDEXED_CHARS
    for value in values:
        cut = truncate_text(value, limit)
        if cut:
            return cut
    return ""


def _web_result(rank: int, item: WebSearchResult) -> WebResultOut:
    return WebResultOut(
        title=item.title,
        url=item.url,
        snippet=_text_at(rank, item.summary, item.snippet),
    )


def _paper(rank: int, paper: EnrichedPaper) -> PaperOut:
    return PaperOut(
        title=paper.title,
        year=paper.year,
        journal=paper.journal_title,
        authors=paper.authors,
        doi=paper.doi,
        pmid=paper.pmid,
        url=paper.url,
        abstract=_text_at(rank, paper.abstract, paper.snippet),
    )


def _web_out(response: WebSearchResponse) -> WebSearchOut:
    return WebSearchOut(
        query=response.query,
        results=[_web_result(i, item) for i, item in enumerate(response.results)],
        guidance=_WEB_GUIDANCE if response.results else "",
        error=response.error,
    )


def _literature_out(response: LiteratureSearchResponse) -> LiteratureSearchOut:
    return LiteratureSearchOut(
        query=response.query,
        results=[_paper(i, paper) for i, paper in enumerate(response.results)],
        guidance=_LITERATURE_GUIDANCE if response.results else "",
    )


async def web_search(
    ctx: RunContext[AgentDeps],
    query: str,
    limit: int = 5,
    include_summary: bool = True,
    summary_max_chars: int = 600,
) -> ToolReturn[WebSearchOut]:
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
    response = await service.search(
        query,
        limit=limit,
        include_summary=include_summary,
        summary_max_chars=summary_max_chars,
    )
    return with_summary(
        _web_out(response),
        f"{len(response.results)} results for {query}",
        ctx=ctx,
        status="ok" if response.results else "empty",
        extra=source_url_chunks_from_citations(list(response.citations)),
    )


async def literature_search(
    ctx: RunContext[AgentDeps],
    query: str,
    limit: int = 8,
    sort: LiteratureSort = "relevance",
    output_options: LiteratureSearchOutputOptions = _DEFAULT_OUTPUT_OPTIONS,
    filters: LiteratureSearchFilters = _DEFAULT_FILTERS,
) -> ToolReturn[LiteratureSearchOut]:
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
    response = await service.search(
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
    return with_summary(
        _literature_out(response),
        f"{len(response.results)} papers for {query}",
        ctx=ctx,
        status="ok" if response.results else "empty",
        extra=source_url_chunks_from_citations(list(response.citations)),
    )
