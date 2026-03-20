"""Crossref API client."""

from typing import cast

import httpx

from veupath_chatbot.platform.errors import ExternalServiceError
from veupath_chatbot.platform.types import JSONObject, JSONValue
from veupath_chatbot.services.research.clients._base import (
    StandardClient,
    make_citation,
)


class CrossrefClient(StandardClient):
    """Client for Crossref API."""

    _source_name = "crossref"

    async def _fetch_raw(self, query: str, *, limit: int) -> list[JSONValue]:
        url = "https://api.crossref.org/works"
        params = {"query": query, "rows": str(limit)}
        headers = {"User-Agent": "pathfinder-planner/1.0 (mailto:unknown@example.com)"}
        try:
            async with httpx.AsyncClient(timeout=self._timeout, headers=headers) as client:
                resp = await client.get(url, params=params, follow_redirects=True)
                resp.raise_for_status()
                payload = resp.json()
        except httpx.HTTPError as exc:
            service = "CrossRef"
            raise ExternalServiceError(service, str(exc)) from exc
        items = (
            payload.get("message", {}).get("items", [])
            if isinstance(payload, dict)
            else []
        )
        return list(items)

    def _parse_item(
        self, raw: JSONValue, *, abstract_max_chars: int
    ) -> tuple[JSONObject, JSONObject] | None:
        if not isinstance(raw, dict):
            return None
        item = raw

        title_list = item.get("title")
        first_title = (
            title_list[0] if isinstance(title_list, list) and title_list else None
        )
        title = first_title.strip() if isinstance(first_title, str) else ""
        doi_raw = item.get("DOI")
        doi: str | None = doi_raw if isinstance(doi_raw, str) else None
        url_raw = item.get("URL")
        url_item: str | None = url_raw if isinstance(url_raw, str) else None

        year_i: int | None = None
        published = item.get("published-print") or item.get("published-online") or {}
        parts = published.get("date-parts") if isinstance(published, dict) else None
        if (
            isinstance(parts, list)
            and parts
            and isinstance(parts[0], list)
            and parts[0]
        ):
            try:
                raw_year = parts[0][0]
                year_i = int(raw_year) if isinstance(raw_year, (int, str)) else None
            except ValueError, TypeError:
                year_i = None

        authors: list[str] | None = None
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

        journal: str | None = None
        ct = item.get("container-title")
        if isinstance(ct, list) and ct:
            journal = str(ct[0]).strip()

        result_url = url_item or (f"https://doi.org/{doi}" if doi else None)

        result: JSONObject = {
            "title": title,
            "year": year_i,
            "doi": doi,
            "url": result_url,
            "authors": cast("JSONValue", authors),
            "journalTitle": journal,
            "snippet": journal,
        }
        citation = make_citation(
            source="crossref",
            id_prefix="crossref",
            title=title or (url_item or "Crossref result"),
            url=result_url,
            authors=authors,
            year=year_i,
            doi=doi,
            snippet=journal,
        )
        return result, citation
