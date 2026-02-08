"""Web search service using DuckDuckGo."""

from __future__ import annotations

import asyncio
import re as _re
from typing import cast

import httpx

from veupath_chatbot.domain.research.citations import (
    Citation,
    _new_citation_id,
    _now_iso,
    ensure_unique_citation_tags,
)
from veupath_chatbot.platform.types import JSONArray, JSONObject, JSONValue
from veupath_chatbot.services.research.utils import (
    candidate_queries,
    decode_ddg_redirect,
    looks_blocked,
    strip_tags,
    truncate_text,
)


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
            async with httpx.AsyncClient(
                timeout=min(self._timeout, 15.0),
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/122.0.0.0 Safari/537.36"
                    ),
                    "Accept": (
                        "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
                    ),
                    "Accept-Language": "en-US,en;q=0.9",
                },
            ) as client:
                summaries = await asyncio.gather(
                    *[
                        self._fetch_page_summary(
                            client,
                            (r.get("url") if isinstance(r, dict) else None)
                            if isinstance(r, dict)
                            else None,
                            max_chars=summary_max_chars,
                        )
                        for r in results
                        if isinstance(r, dict)
                    ],
                    return_exceptions=True,
                )
            for r, s in zip(results, summaries, strict=False):
                if not isinstance(r, dict):
                    continue
                summary = s.strip() if isinstance(s, str) and s.strip() else None
                r["summary"] = cast(JSONValue, summary)
                snip = r.get("snippet")
                if ((not isinstance(snip, str)) or len(snip.strip()) < 40) and summary:
                    r["snippet"] = cast(JSONValue, summary)

        citations: list[JSONObject] = []
        for r in results:
            if not isinstance(r, dict):
                continue
            title_raw = r.get("title")
            url_raw = r.get("url")
            title = (
                title_raw
                if isinstance(title_raw, str)
                else (url_raw if isinstance(url_raw, str) else "Web result")
            )
            snippet_raw = r.get("summary") or r.get("snippet")
            snippet = snippet_raw if isinstance(snippet_raw, str) else None
            citations.append(
                Citation(
                    id=_new_citation_id("web"),
                    source="web",
                    title=title,
                    url=url_raw if isinstance(url_raw, str) else None,
                    snippet=snippet,
                    accessed_at=_now_iso(),
                ).to_dict()
            )
        ensure_unique_citation_tags(citations)
        payload: JSONObject = {
            "query": q,
            "effectiveQuery": effective_query,
            "searchAdjusted": effective_query != q,
            "searchDiagnostics": diag,
            "results": results,
            "citations": cast(JSONValue, citations),
        }
        if not results and isinstance(diag, dict) and diag.get("blocked") is True:
            payload["error"] = "search_blocked"
        return payload

    async def _fetch_page_summary(
        self, client: httpx.AsyncClient, url: JSONValue, *, max_chars: int
    ) -> str | None:
        """Fetch and extract a summary from a web page."""
        if not isinstance(url, str) or not url.strip():
            return None
        u = url.strip()
        if u.lower().endswith(".pdf"):
            return None
        if "scholar.google." in u:
            return None

        try:
            resp = await client.get(
                u,
                follow_redirects=True,
                headers={"Referer": "https://duckduckgo.com/"},
            )
            resp.raise_for_status()
            html = resp.text or ""
        except Exception:
            return None

        meta_patterns = [
            r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+name=["\']twitter:description["\'][^>]+content=["\']([^"\']+)["\']',
        ]
        for pat in meta_patterns:
            m = _re.search(pat, html, flags=_re.IGNORECASE)
            if m:
                txt = strip_tags(m.group(1))
                return truncate_text(txt, max_chars) if txt else None

        paras = _re.findall(
            r"<p[^>]*>(.*?)</p>", html, flags=_re.IGNORECASE | _re.DOTALL
        )
        best: str | None = None
        for p in paras:
            txt = strip_tags(p)
            low = txt.lower()
            if len(txt) < 60:
                continue
            if "toggle navigation" in low or "main navigation" in low:
                continue
            if best is None or len(txt) > len(best):
                best = txt
        return truncate_text(best, max_chars) if best else None

    async def _ddg_html_search(
        self, q: str, *, limit: int
    ) -> tuple[JSONArray, str, JSONObject]:
        """Perform DuckDuckGo HTML search with fallback query variations."""
        url = "https://html.duckduckgo.com/html/"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

        def _parse_results(html: str) -> JSONArray:
            parsed: JSONArray = []
            # Find result links; snippets are nearby in the HTML.
            for m in _re.finditer(
                r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
                html,
                flags=_re.IGNORECASE,
            ):
                if len(parsed) >= limit:
                    break
                href = m.group(1)
                title = _re.sub(r"<[^>]+>", "", m.group(2)).strip()
                if not title:
                    continue
                window = html[m.end() : m.end() + 2000]
                m_snip = _re.search(
                    r'class="result__snippet"[^>]*>(.*?)</',
                    window,
                    flags=_re.IGNORECASE,
                )
                snippet_html = m_snip.group(1) if m_snip else ""
                snippet = _re.sub(r"<[^>]+>", "", snippet_html).strip() or None
                parsed.append(
                    {
                        "title": title,
                        "url": decode_ddg_redirect(href),
                        "snippet": snippet,
                    }
                )
            return parsed

        diag: JSONObject = {
            "blocked": False,
            "attempts": 0,
            "statusCodes": cast(JSONValue, []),
        }
        last_html = ""
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
                    diag["statusCodes"] = cast(JSONValue, [resp.status_code])
                last_html = resp.text or ""
                if looks_blocked(resp.status_code, last_html):
                    diag["blocked"] = True
                    continue
                results = _parse_results(last_html)
                if results:
                    return results, cand, diag

        if last_html and not diag.get("blocked"):
            return _parse_results(last_html), q, diag
        return [], q, diag
