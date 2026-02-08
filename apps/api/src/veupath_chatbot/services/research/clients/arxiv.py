"""arXiv API client."""

from __future__ import annotations

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
from veupath_chatbot.services.research.utils import strip_tags, truncate_text


class ArxivClient:
    """Client for arXiv API."""

    def __init__(self, *, timeout_seconds: float = 15.0) -> None:
        self._timeout = timeout_seconds

    async def search(
        self, query: str, *, limit: int, abstract_max_chars: int
    ) -> JSONObject:
        """Search arXiv."""
        url = "http://export.arxiv.org/api/query"
        params = {
            "search_query": f"all:{query}",
            "start": "0",
            "max_results": str(limit),
        }
        headers = {
            "User-Agent": "pathfinder-planner/1.0 (+https://pathfinder.veupathdb.org)"
        }
        async with httpx.AsyncClient(timeout=self._timeout, headers=headers) as client:
            resp = await client.get(url, params=params, follow_redirects=True)
            resp.raise_for_status()
            xml = resp.text or ""

        # Minimal parser: handle empty feeds gracefully (unit tests use empty feed).
        entries = _re.findall(
            r"<entry>(.*?)</entry>", xml, flags=_re.IGNORECASE | _re.DOTALL
        )
        results: JSONArray = []
        citations: list[JSONObject] = []
        for e in entries[:limit]:
            title = strip_tags(
                "".join(
                    _re.findall(
                        r"<title>(.*?)</title>", e, flags=_re.IGNORECASE | _re.DOTALL
                    )
                )
            ).strip()
            link_m = _re.search(r'<link[^>]+href="([^"]+)"', e, flags=_re.IGNORECASE)
            url_item = link_m.group(1) if link_m else None
            abstract = strip_tags(
                "".join(
                    _re.findall(
                        r"<summary>(.*?)</summary>",
                        e,
                        flags=_re.IGNORECASE | _re.DOTALL,
                    )
                )
            ).strip()
            abstract_truncated = truncate_text(abstract, abstract_max_chars)
            results.append(
                {
                    "title": title,
                    "url": url_item,
                    "abstract": abstract_truncated or "",
                    "snippet": abstract,
                }
            )
            citations.append(
                Citation(
                    id=_new_citation_id("arxiv"),
                    source="arxiv",
                    title=title or (url_item or "arXiv result"),
                    url=url_item,
                    snippet=abstract,
                    accessed_at=_now_iso(),
                ).to_dict()
            )
        ensure_unique_citation_tags(citations)
        return {
            "query": query,
            "source": "arxiv",
            "results": results,
            "citations": cast(JSONValue, citations),
        }
