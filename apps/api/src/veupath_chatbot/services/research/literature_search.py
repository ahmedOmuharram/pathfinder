"""Literature search service orchestrating multiple API clients."""

from __future__ import annotations

import asyncio
import collections.abc
from typing import cast

from veupath_chatbot.domain.research.citations import (
    LiteratureSort,
    LiteratureSource,
    ensure_unique_citation_tags,
)
from veupath_chatbot.platform.types import JSONArray, JSONObject, JSONValue
from veupath_chatbot.services.research.clients import (
    ArxivClient,
    CrossrefClient,
    EuropePmcClient,
    OpenAlexClient,
    PreprintClient,
    PubmedClient,
    SemanticScholarClient,
)
from veupath_chatbot.services.research.utils import (
    dedupe_key,
    limit_authors,
    list_str,
    passes_filters,
    rerank_score,
    truncate_text,
)


class LiteratureSearchService:
    """Service for searching scientific literature across multiple sources."""

    def __init__(self, *, timeout_seconds: float = 15.0) -> None:
        self._timeout = timeout_seconds
        self._europepmc = EuropePmcClient(timeout_seconds=timeout_seconds)
        self._crossref = CrossrefClient(timeout_seconds=timeout_seconds)
        self._openalex = OpenAlexClient(timeout_seconds=timeout_seconds)
        self._semanticscholar = SemanticScholarClient(timeout_seconds=timeout_seconds)
        self._pubmed = PubmedClient(timeout_seconds=timeout_seconds)
        self._arxiv = ArxivClient(timeout_seconds=timeout_seconds)
        self._preprint = PreprintClient(timeout_seconds=timeout_seconds)

    async def search(
        self,
        query: str,
        *,
        source: LiteratureSource = "all",
        limit: int = 5,
        sort: LiteratureSort = "relevance",
        include_abstract: bool = False,
        abstract_max_chars: int = 2000,
        max_authors: int = 2,
        year_from: int | None = None,
        year_to: int | None = None,
        author_includes: str | None = None,
        title_includes: str | None = None,
        journal_includes: str | None = None,
        doi_equals: str | None = None,
        pmid_equals: str | None = None,
        require_doi: bool = False,
    ) -> JSONObject:
        """Search scientific literature across multiple sources."""
        q = (query or "").strip()
        if not q:
            return {"results": [], "citations": [], "error": "query_required"}
        limit = max(1, min(int(limit or 5), 25))
        abstract_max_chars = max(200, min(int(abstract_max_chars or 2000), 10000))
        if max_authors != -1:
            max_authors = max(0, min(int(max_authors or 2), 50))

        by_source: dict[str, JSONObject] = {}

        async def _safe(
            name: str, coro: collections.abc.Awaitable[JSONObject]
        ) -> tuple[str, JSONObject]:
            try:
                res = await coro
                return (
                    name,
                    res if isinstance(res, dict) else {"error": "invalid_response"},
                )
            except Exception as exc:
                return (
                    name,
                    {
                        "query": q,
                        "source": name,
                        "results": [],
                        "citations": [],
                        "error": str(exc),
                    },
                )

        if source == "all":
            pairs = await asyncio.gather(
                _safe(
                    "europepmc",
                    self._europepmc.search(
                        q, limit=limit, abstract_max_chars=abstract_max_chars
                    ),
                ),
                _safe(
                    "crossref",
                    self._crossref.search(
                        q, limit=limit, abstract_max_chars=abstract_max_chars
                    ),
                ),
                _safe(
                    "openalex",
                    self._openalex.search(
                        q, limit=limit, abstract_max_chars=abstract_max_chars
                    ),
                ),
                _safe(
                    "semanticscholar",
                    self._semanticscholar.search(
                        q, limit=limit, abstract_max_chars=abstract_max_chars
                    ),
                ),
                _safe(
                    "pubmed",
                    self._pubmed.search(
                        q,
                        limit=limit,
                        include_abstract=include_abstract,
                        abstract_max_chars=abstract_max_chars,
                    ),
                ),
                _safe(
                    "arxiv",
                    self._arxiv.search(
                        q, limit=limit, abstract_max_chars=abstract_max_chars
                    ),
                ),
                _safe(
                    "biorxiv",
                    self._preprint.search(
                        q,
                        site="biorxiv.org",
                        source="biorxiv",
                        limit=limit,
                        include_abstract=include_abstract,
                        abstract_max_chars=abstract_max_chars,
                    ),
                ),
                _safe(
                    "medrxiv",
                    self._preprint.search(
                        q,
                        site="medrxiv.org",
                        source="medrxiv",
                        limit=limit,
                        include_abstract=include_abstract,
                        abstract_max_chars=abstract_max_chars,
                    ),
                ),
            )
            by_source.update(dict(pairs))
        else:
            # single-source
            if source == "europepmc":
                k, v = await _safe(
                    "europepmc",
                    self._europepmc.search(
                        q, limit=limit, abstract_max_chars=abstract_max_chars
                    ),
                )
            elif source == "crossref":
                k, v = await _safe(
                    "crossref",
                    self._crossref.search(
                        q, limit=limit, abstract_max_chars=abstract_max_chars
                    ),
                )
            elif source == "openalex":
                k, v = await _safe(
                    "openalex",
                    self._openalex.search(
                        q, limit=limit, abstract_max_chars=abstract_max_chars
                    ),
                )
            elif source == "semanticscholar":
                k, v = await _safe(
                    "semanticscholar",
                    self._semanticscholar.search(
                        q, limit=limit, abstract_max_chars=abstract_max_chars
                    ),
                )
            elif source == "pubmed":
                k, v = await _safe(
                    "pubmed",
                    self._pubmed.search(
                        q,
                        limit=limit,
                        include_abstract=include_abstract,
                        abstract_max_chars=abstract_max_chars,
                    ),
                )
            elif source == "arxiv":
                k, v = await _safe(
                    "arxiv",
                    self._arxiv.search(
                        q, limit=limit, abstract_max_chars=abstract_max_chars
                    ),
                )
            elif source == "biorxiv":
                k, v = await _safe(
                    "biorxiv",
                    self._preprint.search(
                        q,
                        site="biorxiv.org",
                        source="biorxiv",
                        limit=limit,
                        include_abstract=include_abstract,
                        abstract_max_chars=abstract_max_chars,
                    ),
                )
            else:  # medrxiv
                k, v = await _safe(
                    "medrxiv",
                    self._preprint.search(
                        q,
                        site="medrxiv.org",
                        source="medrxiv",
                        limit=limit,
                        include_abstract=include_abstract,
                        abstract_max_chars=abstract_max_chars,
                    ),
                )
            by_source[k] = v

        # Merge + filter + dedupe; keep citations aligned via dedupe key.
        filtered: JSONArray = []
        citations_by_key: dict[str, JSONObject] = {}
        seen: set[str] = set()

        for src, source_payload in by_source.items():
            results = (
                source_payload.get("results")
                if isinstance(source_payload, dict)
                else None
            )
            citations = (
                source_payload.get("citations")
                if isinstance(source_payload, dict)
                else None
            )
            if not isinstance(results, list) or not isinstance(citations, list):
                continue
            for i, item in enumerate(results):
                if not isinstance(item, dict):
                    continue
                c = citations[i] if i < len(citations) else None
                title = str(item.get("title") or "").strip()
                authors = (
                    item.get("authors")
                    if isinstance(item.get("authors"), list)
                    else None
                )
                year_raw = item.get("year")
                year = year_raw if isinstance(year_raw, int) else None
                doi_raw = item.get("doi")
                doi = doi_raw if isinstance(doi_raw, str) else None
                pmid_raw = item.get("pmid")
                pmid = pmid_raw if isinstance(pmid_raw, str) else None
                journal = item.get("journalTitle") or item.get("journal")
                journal = str(journal).strip() if journal is not None else None

                if not passes_filters(
                    title=title,
                    authors=list_str(authors) if authors is not None else None,
                    year=year,
                    doi=doi,
                    pmid=pmid,
                    journal=journal,
                    year_from=year_from,
                    year_to=year_to,
                    author_includes=author_includes,
                    title_includes=title_includes,
                    journal_includes=journal_includes,
                    doi_equals=doi_equals,
                    pmid_equals=pmid_equals,
                    require_doi=require_doi,
                ):
                    continue

                key = dedupe_key(item)
                if key in seen:
                    continue
                seen.add(key)
                authors_limited = limit_authors(
                    list_str(authors) if authors else None, max_authors
                )
                abstract_raw = item.get("abstract")
                abstract_value: str | None
                if include_abstract:
                    abstract_str = (
                        abstract_raw if isinstance(abstract_raw, str) else None
                    )
                    abstract_value = truncate_text(abstract_str, abstract_max_chars)
                else:
                    abstract_value = (
                        abstract_raw if isinstance(abstract_raw, str) else None
                    )
                filtered.append(
                    {
                        **item,
                        "source": src,
                        "authors": cast(JSONValue, authors_limited),
                        "abstract": abstract_value,
                    }
                )

                if isinstance(c, dict):
                    c2: JSONObject = {**c}
                    authors_raw = c2.get("authors")
                    if authors_raw is not None:
                        authors_list = list_str(authors_raw)
                        authors_limited = limit_authors(authors_list, max_authors)
                        c2["authors"] = cast(JSONValue, authors_limited)
                    citations_by_key[key] = c2

        if sort == "newest":

            def get_year_key(r: JSONValue) -> tuple[bool, int]:
                if not isinstance(r, dict):
                    return (False, 0)
                year_raw = r.get("year")
                year = year_raw if isinstance(year_raw, int) else None
                return (year is not None, year if year is not None else 0)

            filtered.sort(key=get_year_key, reverse=True)

        def _ordered_citations(
            results_list: JSONArray,
        ) -> list[JSONObject]:
            ordered: list[JSONObject] = []
            for r in results_list:
                if not isinstance(r, dict):
                    continue
                key = dedupe_key(r)
                c = citations_by_key.get(key)
                if isinstance(c, dict):
                    ordered.append(c)
            return ordered

        payload: JSONObject = {
            "query": q,
            "source": source,
            "sort": sort,
            "includeAbstract": include_abstract,
            "abstractMaxChars": abstract_max_chars,
            "maxAuthors": max_authors,
            "filters": {
                "yearFrom": year_from,
                "yearTo": year_to,
                "authorIncludes": author_includes,
                "titleIncludes": title_includes,
                "journalIncludes": journal_includes,
                "doiEquals": doi_equals,
                "pmidEquals": pmid_equals,
                "requireDoi": require_doi,
            },
            "results": filtered[:limit],
            "citations": cast(JSONValue, _ordered_citations(filtered)),
        }

        if sort == "relevance" and source == "all" and filtered:
            scored: JSONArray = []
            for item in filtered:
                if not isinstance(item, dict):
                    continue
                score, parts = rerank_score(q, item)
                scored.append(
                    {
                        **item,
                        "score": round(score, 2),
                        "scoreParts": cast(JSONValue, parts),
                    }
                )

            def get_score_key(r: JSONValue) -> tuple[bool, float]:
                if not isinstance(r, dict):
                    return (False, 0.0)
                score_raw = r.get("score")
                score_val = score_raw if isinstance(score_raw, (int, float)) else None
                return (
                    score_val is not None,
                    float(score_val) if score_val is not None else 0.0,
                )

            scored.sort(key=get_score_key, reverse=True)
            filtered = scored
            payload["results"] = filtered[:limit]
            payload["citations"] = cast(JSONValue, _ordered_citations(filtered))

        if source == "all":
            payload["bySource"] = cast(JSONValue, by_source)
        citations_raw = payload.get("citations")
        if isinstance(citations_raw, list):
            citations_list: list[JSONObject] = [
                c for c in citations_raw if isinstance(c, dict)
            ]
            ensure_unique_citation_tags(citations_list)
        return payload
