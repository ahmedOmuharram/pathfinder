"""Web search service using DuckDuckGo."""

import asyncio
import re
from typing import cast

import httpx

from veupath_chatbot.domain.research.citations import ensure_unique_citation_tags
from veupath_chatbot.platform.errors import ExternalServiceError
from veupath_chatbot.platform.types import JSONArray, JSONObject, JSONValue
from veupath_chatbot.services.research.clients._base import make_citation
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


def _parse_ddg_results(html: str, *, limit: int) -> JSONArray:
    """Parse DuckDuckGo HTML search results into structured items."""
    parsed: JSONArray = []
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
            {
                "title": title,
                "url": decode_ddg_redirect(href),
                "snippet": snippet,
            }
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
    ) -> JSONObject:
        """Search the web and return results with citations."""
        q = (query or "").strip()
        if not q:
            return {"results": [], "citations": [], "error": "query_required"}
        limit = max(1, min(int(limit or 5), 10))
        summary_max_chars = max(200, min(int(summary_max_chars or 600), 4000))

        results, effective_query, diag = await self._ddg_html_search(q, limit=limit)
        if include_summary and results:
            dict_results = [r for r in results if isinstance(r, dict)]
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
                            r.get("url"),
                            max_chars=summary_max_chars,
                        )
                        for r in dict_results
                    ],
                    return_exceptions=True,
                )
            for r, s in zip(dict_results, summaries, strict=True):
                summary = s.strip() if isinstance(s, str) and s.strip() else None
                r["summary"] = cast("JSONValue", summary)
                snip = r.get("snippet")
                if (
                    (not isinstance(snip, str))
                    or len(snip.strip()) < _MIN_SNIPPET_LENGTH
                ) and summary:
                    r["snippet"] = cast("JSONValue", summary)

        citations: list[JSONObject] = []
        for item in results:
            if not isinstance(item, dict):
                continue
            title_raw = item.get("title")
            url_raw = item.get("url")
            title = (
                title_raw
                if isinstance(title_raw, str)
                else (url_raw if isinstance(url_raw, str) else "Web result")
            )
            snippet_raw = item.get("summary") or item.get("snippet")
            snippet = snippet_raw if isinstance(snippet_raw, str) else None
            citations.append(
                make_citation(
                    source="web",
                    id_prefix="web",
                    title=title,
                    url=url_raw if isinstance(url_raw, str) else None,
                    snippet=snippet,
                )
            )
        ensure_unique_citation_tags(citations)
        payload: JSONObject = {
            "query": q,
            "effectiveQuery": effective_query,
            "searchAdjusted": effective_query != q,
            "searchDiagnostics": diag,
            "results": results,
            "citations": cast("JSONValue", citations),
        }
        if not results and isinstance(diag, dict) and diag.get("blocked") is True:
            payload["error"] = "search_blocked"
        return payload

    async def _ddg_html_search(
        self, q: str, *, limit: int
    ) -> tuple[JSONArray, str, JSONObject]:
        """Perform DuckDuckGo HTML search with fallback query variations."""
        url = "https://html.duckduckgo.com/html/"
        headers = {
            "User-Agent": BROWSER_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

        diag: JSONObject = {
            "blocked": False,
            "attempts": 0,
            "statusCodes": cast("JSONValue", []),
        }
        last_html = ""
        try:
            async with httpx.AsyncClient(timeout=self._timeout, headers=headers) as client:
                for cand in candidate_queries(q):
                    resp = await client.get(url, params={"q": cand}, follow_redirects=True)
                    attempts_raw = diag.get("attempts")
                    attempts = (
                        int(attempts_raw) if isinstance(attempts_raw, (int, float)) else 0
                    )
                    diag["attempts"] = attempts + 1
                    status_codes_raw = diag.get("statusCodes")
                    if isinstance(status_codes_raw, list):
                        status_codes_raw.append(resp.status_code)
                    else:
                        diag["statusCodes"] = cast("JSONValue", [resp.status_code])
                    last_html = resp.text or ""
                    if looks_blocked(resp.status_code, last_html):
                        diag["blocked"] = True
                        continue
                    results = _parse_ddg_results(last_html, limit=limit)
                    if results:
                        return results, cand, diag
        except httpx.HTTPError as exc:
            service = "DuckDuckGo (web search)"
            raise ExternalServiceError(service, str(exc)) from exc

        if last_html and not diag.get("blocked"):
            return _parse_ddg_results(last_html, limit=limit), q, diag
        return [], q, diag
