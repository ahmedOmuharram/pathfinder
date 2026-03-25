"""Preprint site search client (bioRxiv, medRxiv)."""

import asyncio
import re
from typing import Literal

import httpx

from veupath_chatbot.domain.research.citations import (
    Citation,
    _new_citation_id,
    _now_iso,
)
from veupath_chatbot.platform.errors import ExternalServiceError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject, JSONValue
from veupath_chatbot.services.research.clients._base import (
    BaseClient,
    build_response,
)
from veupath_chatbot.services.research.utils import (
    BROWSER_USER_AGENT,
    decode_ddg_redirect,
    fetch_page_summary,
    strip_tags,
)

logger = get_logger(__name__)

_MAX_RETRIES = 3
_BACKOFF_BASE_S = 2.0


class PreprintClient(BaseClient):
    """Client for preprint site searches via DuckDuckGo.

    Preprint search has a unique signature (``site``, ``source``,
    ``include_abstract``) and a post-processing step that fetches page
    summaries, so it keeps a custom ``search`` method.  Per-item parsing
    still goes through ``_parse_item`` / ``_build_results``.
    """

    _current_source: Literal["biorxiv", "medrxiv"] = "biorxiv"

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
        """Search preprint sites using DuckDuckGo with retry on 429."""
        last_exc: Exception | None = None
        raw_items: list[JSONValue] = []
        for attempt in range(_MAX_RETRIES):
            try:
                raw_items = await self._fetch_raw(query, site=site, limit=limit)
                break
            except ExternalServiceError as exc:
                last_exc = exc
                if "429" in str(exc):
                    wait = _BACKOFF_BASE_S * (2 ** attempt)
                    logger.warning(
                        "DuckDuckGo 429, retrying",
                        attempt=attempt + 1,
                        wait_s=wait,
                    )
                    await asyncio.sleep(wait)
                    continue
                raise
        else:
            raise ExternalServiceError("DuckDuckGo", str(last_exc))
        self._current_source: Literal["biorxiv", "medrxiv"] = source
        results, citations = self._build_results(
            raw_items, abstract_max_chars=abstract_max_chars
        )

        if include_abstract and results:
            dict_results = [r for r in results if isinstance(r, dict)]
            async with httpx.AsyncClient(
                timeout=min(self._timeout, 15.0),
                headers={
                    "User-Agent": BROWSER_USER_AGENT,
                    "Accept-Language": "en-US,en;q=0.9",
                },
            ) as client:
                summaries = await asyncio.gather(
                    *[
                        fetch_page_summary(
                            client, r.get("url"), max_chars=abstract_max_chars
                        )
                        for r in dict_results
                    ],
                    return_exceptions=True,
                )
            for r, s in zip(dict_results, summaries, strict=True):
                if isinstance(s, str) and s.strip():
                    r["abstract"] = s.strip()
                    r["snippet"] = s.strip()

        return build_response(
            query=query, source=source, results=results, citations=citations
        )

    # -- fetch -------------------------------------------------------------

    async def _fetch_raw(self, query: str, *, site: str, limit: int) -> list[JSONValue]:
        ddg_url = "https://duckduckgo.com/html/"
        params = {"q": f"site:{site} {query}"}
        headers = {"User-Agent": "pathfinder-planner/1.0"}
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, headers=headers
            ) as client:
                resp = await client.get(ddg_url, params=params, follow_redirects=True)
                resp.raise_for_status()
                html = resp.text or ""
        except httpx.HTTPError as exc:
            service = "DuckDuckGo (preprint search)"
            raise ExternalServiceError(service, str(exc)) from exc

        items: list[JSONValue] = []
        for m in re.finditer(
            r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
            html,
            flags=re.IGNORECASE,
        ):
            if len(items) >= limit:
                break
            items.append(
                {
                    "_title": strip_tags(m.group(2)),
                    "_url": decode_ddg_redirect(m.group(1)),
                }
            )
        return items

    # -- parse -------------------------------------------------------------

    def _parse_item(
        self, raw: JSONValue, *, abstract_max_chars: int
    ) -> tuple[JSONObject, JSONObject] | None:
        if not isinstance(raw, dict):
            return None
        title = str(raw.get("_title") or "")
        url_str = raw.get("_url")
        url_str = url_str if isinstance(url_str, str) else None
        source = self._current_source

        result: JSONObject = {"title": title, "url": url_str, "snippet": None}
        citation = Citation(
            id=_new_citation_id(source),
            source=source,
            title=title or (url_str or f"{source} result"),
            url=url_str,
            accessed_at=_now_iso(),
        ).model_dump(by_alias=True, exclude_none=True, mode="json")
        return result, citation
