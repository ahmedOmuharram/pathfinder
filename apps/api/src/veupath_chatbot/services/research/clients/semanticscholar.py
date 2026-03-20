"""Semantic Scholar API client."""

from typing import cast

import httpx

from veupath_chatbot.domain.research.citations import (
    Citation,
    _new_citation_id,
    _now_iso,
)
from veupath_chatbot.platform.errors import ExternalServiceError
from veupath_chatbot.platform.types import JSONObject, JSONValue
from veupath_chatbot.services.research.clients._base import (
    API_USER_AGENT,
    StandardClient,
)
from veupath_chatbot.services.research.utils import truncate_text


class SemanticScholarClient(StandardClient):
    """Client for Semantic Scholar API."""

    _source_name = "semanticscholar"

    async def _fetch_raw(self, query: str, *, limit: int) -> list[JSONValue]:
        url = "https://api.semanticscholar.org/graph/v1/paper/search"
        params = {
            "query": query,
            "limit": str(limit),
            "fields": "title,year,authors,url,abstract,journal,externalIds",
        }
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, headers={"User-Agent": API_USER_AGENT}
            ) as client:
                resp = await client.get(url, params=params, follow_redirects=True)
                resp.raise_for_status()
                payload = resp.json()
        except httpx.HTTPError as exc:
            service = "Semantic Scholar"
            raise ExternalServiceError(service, str(exc)) from exc
        items = payload.get("data", []) if isinstance(payload, dict) else []
        return list(items)

    def _parse_item(
        self, raw: JSONValue, *, abstract_max_chars: int
    ) -> tuple[JSONObject, JSONObject] | None:
        if not isinstance(raw, dict):
            return None
        item = raw

        title = str(item.get("title") or "").strip()
        year_raw = item.get("year")
        year: int | None = year_raw if isinstance(year_raw, int) else None
        url_val = item.get("url")
        url_item: str | None = url_val if isinstance(url_val, str) else None

        authors: list[str] | None = None
        raw_authors = item.get("authors")
        if isinstance(raw_authors, list):
            authors = [
                str(a.get("name"))
                for a in raw_authors
                if isinstance(a, dict) and a.get("name")
            ]

        abstract_raw = item.get("abstract")
        abstract = truncate_text(
            abstract_raw if isinstance(abstract_raw, str) else None, abstract_max_chars
        )

        journal: str | None = None
        j = item.get("journal")
        if isinstance(j, dict) and j.get("name"):
            journal = str(j.get("name"))

        ext = item.get("externalIds")
        doi: str | None = None
        pmid: str | None = None
        if isinstance(ext, dict):
            doi_val = ext.get("DOI")
            if isinstance(doi_val, str):
                doi = doi_val
            pmid_val = ext.get("PubMed")
            if isinstance(pmid_val, str):
                pmid = pmid_val

        result_url = url_item or (f"https://doi.org/{doi}" if doi else None)

        result: JSONObject = {
            "title": title,
            "year": year,
            "doi": doi,
            "pmid": pmid,
            "url": result_url,
            "authors": cast("JSONValue", authors),
            "journalTitle": journal,
            "abstract": abstract,
            "snippet": abstract or journal,
        }
        citation = Citation(
            id=_new_citation_id("s2"),
            source="semanticscholar",
            title=title or (url_item or "Semantic Scholar result"),
            url=result_url,
            authors=authors,
            year=year,
            doi=doi,
            pmid=pmid,
            snippet=abstract or journal,
            accessed_at=_now_iso(),
        ).to_dict()
        return result, citation
