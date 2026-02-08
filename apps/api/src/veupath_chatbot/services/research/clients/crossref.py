"""Crossref API client."""

from __future__ import annotations

from typing import cast

import httpx

from veupath_chatbot.domain.research.citations import (
    Citation,
    _new_citation_id,
    _now_iso,
    ensure_unique_citation_tags,
)
from veupath_chatbot.platform.types import JSONArray, JSONObject, JSONValue


class CrossrefClient:
    """Client for Crossref API."""

    def __init__(self, *, timeout_seconds: float = 15.0) -> None:
        self._timeout = timeout_seconds

    async def search(
        self, query: str, *, limit: int, abstract_max_chars: int
    ) -> JSONObject:
        """Search Crossref."""
        url = "https://api.crossref.org/works"
        params = {"query": query, "rows": str(limit)}
        headers = {"User-Agent": "pathfinder-planner/1.0 (mailto:unknown@example.com)"}
        async with httpx.AsyncClient(timeout=self._timeout, headers=headers) as client:
            resp = await client.get(url, params=params, follow_redirects=True)
            resp.raise_for_status()
            payload = resp.json()

        items = (
            payload.get("message", {}).get("items", [])
            if isinstance(payload, dict)
            else []
        )
        results: JSONArray = []
        citations: list[JSONObject] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            title_list = item.get("title")
            title = (
                title_list[0].strip()
                if isinstance(title_list, list) and title_list
                else ""
            )
            doi = item.get("DOI") if isinstance(item.get("DOI"), str) else None
            url_item = item.get("URL") if isinstance(item.get("URL"), str) else None
            year_i: int | None = None
            published = (
                item.get("published-print") or item.get("published-online") or {}
            )
            parts = published.get("date-parts") if isinstance(published, dict) else None
            if (
                isinstance(parts, list)
                and parts
                and isinstance(parts[0], list)
                and parts[0]
            ):
                try:
                    year_i = int(parts[0][0])
                except Exception:
                    year_i = None
            authors = None
            raw_authors = item.get("author")
            if isinstance(raw_authors, list):
                authors = []
                for a in raw_authors:
                    if not isinstance(a, dict):
                        continue
                    family = a.get("family")
                    given = a.get("given")
                    if family and given:
                        authors.append(f"{given} {family}")
                    elif family:
                        authors.append(str(family))
            journal = None
            ct = item.get("container-title")
            if isinstance(ct, list) and ct:
                journal = str(ct[0]).strip()

            results.append(
                {
                    "title": title,
                    "year": year_i,
                    "doi": doi,
                    "url": url_item or (f"https://doi.org/{doi}" if doi else None),
                    "authors": cast(JSONValue, authors),
                    "journalTitle": journal,
                    "snippet": journal,
                }
            )
            citations.append(
                Citation(
                    id=_new_citation_id("crossref"),
                    source="crossref",
                    title=title or (url_item or "Crossref result"),
                    url=url_item or (f"https://doi.org/{doi}" if doi else None),
                    authors=authors,
                    year=year_i,
                    doi=doi,
                    snippet=journal,
                    accessed_at=_now_iso(),
                ).to_dict()
            )
        ensure_unique_citation_tags(citations)
        return {
            "query": query,
            "source": "crossref",
            "results": results,
            "citations": cast(JSONValue, citations),
        }
