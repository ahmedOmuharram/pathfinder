"""Preprint site search client (bioRxiv, medRxiv)."""

from __future__ import annotations

import asyncio
import re as _re
from typing import Literal, cast

import httpx

from veupath_chatbot.domain.research.citations import (
    Citation,
    _new_citation_id,
    _now_iso,
    ensure_unique_citation_tags,
)
from veupath_chatbot.platform.types import JSONArray, JSONObject, JSONValue
from veupath_chatbot.services.research.utils import (
    decode_ddg_redirect,
    strip_tags,
    truncate_text,
)


class PreprintClient:
    """Client for preprint site searches via DuckDuckGo."""

    def __init__(self, *, timeout_seconds: float = 15.0) -> None:
        self._timeout = timeout_seconds

    async def search(
        self,
        query: str,
        *,
        site: str,
        source: Literal["biorxiv", "medrxiv"],
        limit: int,
        include_abstract: bool,
        abstract_max_chars: int,
    ) -> JSONObject:
        """Search preprint sites using DuckDuckGo."""
        # Use DDG HTML endpoint (tests mock duckduckgo.com/html/ for preprints).
        ddg_url = "https://duckduckgo.com/html/"
        params = {"q": f"site:{site} {query}"}
        headers = {
            "User-Agent": "pathfinder-planner/1.0 (+https://pathfinder.veupathdb.org)"
        }
        async with httpx.AsyncClient(timeout=self._timeout, headers=headers) as client:
            resp = await client.get(ddg_url, params=params, follow_redirects=True)
            resp.raise_for_status()
            html = resp.text or ""

        # Reuse the simple result parser shape.
        results: JSONArray = []
        citations: list[JSONObject] = []
        for m in _re.finditer(
            r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
            html,
            flags=_re.IGNORECASE,
        ):
            if len(results) >= limit:
                break
            href = m.group(1)
            title = strip_tags(m.group(2))
            url_item = decode_ddg_redirect(href)
            results.append({"title": title, "url": url_item, "snippet": None})
            citations.append(
                Citation(
                    id=_new_citation_id(source),
                    source=source,
                    title=title or (url_item or f"{source} result"),
                    url=url_item,
                    snippet=None,
                    accessed_at=_now_iso(),
                ).to_dict()
            )

        # Optional: fetch a summary if requested (best-effort).
        if include_abstract and results:
            async with httpx.AsyncClient(
                timeout=min(self._timeout, 15.0),
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/122.0.0.0 Safari/537.36"
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
                            max_chars=abstract_max_chars,
                        )
                        for r in results
                        if isinstance(r, dict)
                    ],
                    return_exceptions=True,
                )
            for r, s in zip(results, summaries, strict=False):
                if not isinstance(r, dict):
                    continue
                if isinstance(s, str) and s.strip():
                    r["abstract"] = s.strip()
                    r["snippet"] = s.strip()

        ensure_unique_citation_tags(citations)
        return {
            "query": query,
            "source": source,
            "results": results,
            "citations": cast(JSONValue, citations),
        }

    async def _fetch_page_summary(
        self, client: httpx.AsyncClient, url: JSONValue, *, max_chars: int
    ) -> str | None:
        """Fetch and extract a summary from a preprint page."""
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
