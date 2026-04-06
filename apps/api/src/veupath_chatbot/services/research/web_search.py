"""Web search service using DuckDuckGo."""

import asyncio
import re
from dataclasses import dataclass, field

import httpx
from pydantic import Field

from veupath_chatbot.domain.research.citations import (
    Citation,
    _new_citation_id,
    _now_iso,
    ensure_unique_citation_tags,
)
from veupath_chatbot.platform.errors import ExternalServiceError
from veupath_chatbot.platform.pydantic_base import CamelModel
from veupath_chatbot.services.research.utils import (
    BROWSER_USER_AGENT,
    candidate_queries,
    decode_ddg_redirect,
    fetch_page_summary,
    looks_blocked,
    strip_tags,
)

# DuckDuckGo sometimes returns very short or empty snippets; replace
# them with the fetched page summary for a more useful search result.
_MIN_SNIPPET_LENGTH = 40


class WebSearchResult(CamelModel):
    """One result from a web search."""

    title: str = ""
    url: str | None = None
    snippet: str | None = None
    summary: str | None = None


class SearchDiagnostics(CamelModel):
    """Diagnostics from a DuckDuckGo search attempt."""

    blocked: bool = False
    attempts: int = 0
    status_codes: list[int] = Field(default_factory=list)


class WebSearchResponse(CamelModel):
    """Full response from the web search service."""

    query: str
    effective_query: str
    search_adjusted: bool
    search_diagnostics: SearchDiagnostics
    results: list[WebSearchResult]
    citations: list[Citation]
    error: str | None = None


@dataclass
class _DiagnosticsTracker:
    """Mutable diagnostics tracker for DuckDuckGo search attempts."""

    blocked: bool = False
    attempts: int = 0
    status_codes: list[int] = field(default_factory=list)

    def to_model(self) -> SearchDiagnostics:
        return SearchDiagnostics(
            blocked=self.blocked,
            attempts=self.attempts,
            status_codes=list(self.status_codes),
        )


def _parse_ddg_results(html: str, *, limit: int) -> list[WebSearchResult]:
    """Parse DuckDuckGo HTML search results into structured items."""
    parsed: list[WebSearchResult] = []
    for m in re.finditer(
        r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        html,
        flags=re.IGNORECASE,
    ):
        if len(parsed) >= limit:
            break
        href = m.group(1)
        title = strip_tags(m.group(2))
        if not title:
            continue
        window = html[m.end() : m.end() + 2000]
        m_snip = re.search(
            r'class="result__snippet"[^>]*>(.*?)</',
            window,
            flags=re.IGNORECASE,
        )
        snippet_html = m_snip.group(1) if m_snip else ""
        snippet = strip_tags(snippet_html) or None
        parsed.append(
            WebSearchResult(
                title=title,
                url=decode_ddg_redirect(href),
                snippet=snippet,
            )
        )
    return parsed


class WebSearchService:
    """Service for web search using DuckDuckGo HTML interface."""

    def __init__(self, *, timeout_seconds: float = 15.0) -> None:
        self._timeout = timeout_seconds

    async def search(
        self,
        query: str,
        limit: int = 5,
        *,
        include_summary: bool = False,
        summary_max_chars: int = 600,
    ) -> WebSearchResponse:
        """Search the web and return results with citations."""
        q = (query or "").strip()
        if not q:
            return WebSearchResponse(
                query=q,
                effective_query=q,
                search_adjusted=False,
                search_diagnostics=SearchDiagnostics(),
                results=[],
                citations=[],
                error="query_required",
            )
        limit = max(1, min(int(limit or 5), 10))
        summary_max_chars = max(200, min(int(summary_max_chars or 600), 4000))

        results, effective_query, diag = await self._ddg_html_search(q, limit=limit)
        if include_summary and results:
            async with httpx.AsyncClient(
                timeout=min(self._timeout, 15.0),
                headers={
                    "User-Agent": BROWSER_USER_AGENT,
                    "Accept": (
                        "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
                    ),
                    "Accept-Language": "en-US,en;q=0.9",
                },
            ) as client:
                summaries = await asyncio.gather(
                    *[
                        fetch_page_summary(
                            client,
                            r.url,
                            max_chars=summary_max_chars,
                        )
                        for r in results
                    ],
                    return_exceptions=True,
                )
            for r, s in zip(results, summaries, strict=True):
                # isinstance(s, str) is legitimate: asyncio.gather(return_exceptions=True)
                # mixes str results with Exception objects in the same list.
                summary = s.strip() if isinstance(s, str) and s.strip() else None
                r.summary = summary
                if (
                    not r.snippet
                    or len(r.snippet.strip()) < _MIN_SNIPPET_LENGTH
                ) and summary:
                    r.snippet = summary

        citations: list[Citation] = []
        for item in results:
            title = item.title or item.url or "Web result"
            snippet = item.summary or item.snippet
            citations.append(
                Citation(
                    id=_new_citation_id("web"),
                    source="web",
                    title=title,
                    url=item.url,
                    snippet=snippet,
                    accessed_at=_now_iso(),
                )
            )
        ensure_unique_citation_tags(citations)

        error: str | None = None
        if not results and diag.blocked:
            error = "search_blocked"

        return WebSearchResponse(
            query=q,
            effective_query=effective_query,
            search_adjusted=effective_query != q,
            search_diagnostics=diag.to_model(),
            results=results,
            citations=citations,
            error=error,
        )

    async def _ddg_html_search(
        self, q: str, *, limit: int
    ) -> tuple[list[WebSearchResult], str, _DiagnosticsTracker]:
        """Perform DuckDuckGo HTML search with fallback query variations."""
        url = "https://html.duckduckgo.com/html/"
        headers = {
            "User-Agent": BROWSER_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

        diag = _DiagnosticsTracker()
        last_html = ""
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, headers=headers
            ) as client:
                for cand in candidate_queries(q):
                    resp = await client.get(
                        url, params={"q": cand}, follow_redirects=True
                    )
                    diag.attempts += 1
                    diag.status_codes.append(resp.status_code)
                    last_html = resp.text or ""
                    if looks_blocked(resp.status_code, last_html):
                        diag.blocked = True
                        continue
                    results = _parse_ddg_results(last_html, limit=limit)
                    if results:
                        return results, cand, diag
        except httpx.HTTPError as exc:
            service = "DuckDuckGo (web search)"
            raise ExternalServiceError(service, str(exc)) from exc

        if last_html and not diag.blocked:
            return _parse_ddg_results(last_html, limit=limit), q, diag
        return [], q, diag
