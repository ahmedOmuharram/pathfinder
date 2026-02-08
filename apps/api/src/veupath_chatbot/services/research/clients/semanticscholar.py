"""Semantic Scholar API client."""

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
from veupath_chatbot.services.research.utils import truncate_text


class SemanticScholarClient:
    """Client for Semantic Scholar API."""

    def __init__(self, *, timeout_seconds: float = 15.0) -> None:
        self._timeout = timeout_seconds

    async def search(
        self, query: str, *, limit: int, abstract_max_chars: int
    ) -> JSONObject:
        """Search Semantic Scholar."""
        url = "https://api.semanticscholar.org/graph/v1/paper/search"
        params = {
            "query": query,
            "limit": str(limit),
            "fields": "title,year,authors,url,abstract,journal,externalIds",
        }
        headers = {
            "User-Agent": "pathfinder-planner/1.0 (+https://pathfinder.veupathdb.org)"
        }
        async with httpx.AsyncClient(timeout=self._timeout, headers=headers) as client:
            resp = await client.get(url, params=params, follow_redirects=True)
            resp.raise_for_status()
            payload = resp.json()

        items = payload.get("data", []) if isinstance(payload, dict) else []
        results: JSONArray = []
        citations: list[JSONObject] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            year = item.get("year") if isinstance(item.get("year"), int) else None
            url_item = item.get("url") if isinstance(item.get("url"), str) else None
            authors = None
            raw_authors = item.get("authors")
            if isinstance(raw_authors, list):
                authors = [
                    str(a.get("name"))
                    for a in raw_authors
                    if isinstance(a, dict) and a.get("name")
                ]
            abstract = (
                item.get("abstract") if isinstance(item.get("abstract"), str) else None
            )
            abstract = truncate_text(abstract, abstract_max_chars)
            journal = None
            j = item.get("journal")
            if isinstance(j, dict) and j.get("name"):
                journal = str(j.get("name"))
            ext = item.get("externalIds")
            doi = None
            pmid = None
            if isinstance(ext, dict):
                if isinstance(ext.get("DOI"), str):
                    doi = ext.get("DOI")
                if isinstance(ext.get("PubMed"), str):
                    pmid = ext.get("PubMed")

            results.append(
                {
                    "title": title,
                    "year": year,
                    "doi": doi,
                    "pmid": pmid,
                    "url": url_item or (f"https://doi.org/{doi}" if doi else None),
                    "authors": cast(JSONValue, authors),
                    "journalTitle": journal,
                    "abstract": abstract,
                    "snippet": abstract or journal,
                }
            )
            citations.append(
                Citation(
                    id=_new_citation_id("s2"),
                    source="semanticscholar",
                    title=title or (url_item or "Semantic Scholar result"),
                    url=url_item or (f"https://doi.org/{doi}" if doi else None),
                    authors=authors,
                    year=year,
                    doi=doi,
                    pmid=pmid,
                    snippet=abstract or journal,
                    accessed_at=_now_iso(),
                ).to_dict()
            )
        ensure_unique_citation_tags(citations)
        return {
            "query": query,
            "source": "semanticscholar",
            "results": results,
            "citations": cast(JSONValue, citations),
        }
