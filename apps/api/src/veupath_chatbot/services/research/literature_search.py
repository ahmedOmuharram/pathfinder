"""Literature search service orchestrating multiple API clients."""

import asyncio
import collections.abc
from dataclasses import dataclass
from typing import ClassVar, Literal, cast

import httpx

from veupath_chatbot.domain.research.citations import (
    LiteratureFilters,
    LiteratureOutputOptions,
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
    LiteratureItemContext,
    dedupe_key,
    limit_authors,
    list_str,
    passes_filters,
    rerank_score,
    truncate_text,
)


@dataclass
class LiteratureResultData:
    """Aggregated result data for response assembly."""

    results: JSONArray
    citations_by_key: dict[str, JSONObject]
    by_source: dict[str, JSONObject]
    limit: int


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

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def search(
        self,
        query: str,
        *,
        source: LiteratureSource = "all",
        limit: int = 5,
        sort: LiteratureSort = "relevance",
        options: LiteratureOutputOptions | None = None,
        filters: LiteratureFilters | None = None,
    ) -> JSONObject:
        """Search scientific literature across multiple sources."""
        if options is None:
            options = LiteratureOutputOptions()
        if filters is None:
            filters = LiteratureFilters()

        error = self._validate_inputs(
            query,
            limit=limit,
            abstract_max_chars=options.abstract_max_chars,
            max_authors=options.max_authors,
        )
        if error is not None:
            return error

        q = query.strip()
        limit = max(1, min(int(limit or 5), 25))
        abstract_max_chars = max(
            200, min(int(options.abstract_max_chars or 2000), 10000)
        )
        max_authors = options.max_authors
        if max_authors != -1:
            max_authors = max(0, min(int(max_authors or 2), 50))
        options = LiteratureOutputOptions(
            include_abstract=options.include_abstract,
            abstract_max_chars=abstract_max_chars,
            max_authors=max_authors,
        )

        by_source = await self._dispatch_sources(
            query=q,
            source=source,
            limit=limit,
            include_abstract=options.include_abstract,
            abstract_max_chars=options.abstract_max_chars,
        )

        filtered, citations_by_key = self._deduplicate_and_filter(
            by_source=by_source,
            options=options,
            filters=filters,
        )

        sorted_results = self._sort_results(filtered, sort=sort, source=source, query=q)

        return self._build_response(
            query=q,
            source=source,
            sort=sort,
            options=options,
            filters=filters,
            result_data=LiteratureResultData(
                results=sorted_results,
                citations_by_key=citations_by_key,
                by_source=by_source,
                limit=limit,
            ),
        )

    # ------------------------------------------------------------------
    # Input validation
    # ------------------------------------------------------------------

    def _validate_inputs(
        self,
        query: str,
        *,
        limit: int,
        abstract_max_chars: int,
        max_authors: int,
    ) -> JSONObject | None:
        """Return an error payload if the query is empty, else None."""
        q = (query or "").strip()
        if not q:
            return {"results": [], "citations": [], "error": "query_required"}
        return None

    # ------------------------------------------------------------------
    # Source dispatch
    # ------------------------------------------------------------------

    _ALL_SOURCE_NAMES: ClassVar[list[str]] = [
        "europepmc",
        "crossref",
        "openalex",
        "semanticscholar",
        "pubmed",
        "arxiv",
        "biorxiv",
        "medrxiv",
    ]

    def _build_source_tasks(
        self,
        *,
        query: str,
        source: LiteratureSource,
        limit: int,
        include_abstract: bool,
        abstract_max_chars: int,
    ) -> list[tuple[str, collections.abc.Awaitable[JSONObject]]]:
        """Build (name, coroutine) pairs for the requested sources.

        Only creates coroutines for sources that will actually be dispatched,
        avoiding unawaited-coroutine warnings when a single source is selected.
        """
        names = self._ALL_SOURCE_NAMES if source == "all" else [source]
        return [
            self._make_source_task(
                name=name,
                query=query,
                limit=limit,
                include_abstract=include_abstract,
                abstract_max_chars=abstract_max_chars,
            )
            for name in names
        ]

    def _make_source_task(
        self,
        *,
        name: str,
        query: str,
        limit: int,
        include_abstract: bool,
        abstract_max_chars: int,
    ) -> tuple[str, collections.abc.Awaitable[JSONObject]]:
        """Create a (name, coroutine) pair for a single source."""
        standard_sources = {
            "europepmc": self._europepmc,
            "crossref": self._crossref,
            "openalex": self._openalex,
            "semanticscholar": self._semanticscholar,
            "arxiv": self._arxiv,
        }
        if name in standard_sources:
            coro = standard_sources[name].search(
                query, limit=limit, abstract_max_chars=abstract_max_chars
            )
        elif name == "pubmed":
            coro = self._pubmed.search(
                query,
                limit=limit,
                include_abstract=include_abstract,
                abstract_max_chars=abstract_max_chars,
            )
        else:
            site = "biorxiv.org" if name == "biorxiv" else "medrxiv.org"
            preprint_source = cast("Literal['biorxiv', 'medrxiv']", name)
            coro = self._preprint.search(
                query,
                site=site,
                source=preprint_source,
                limit=limit,
                include_abstract=include_abstract,
                abstract_max_chars=abstract_max_chars,
            )
        return (name, coro)

    async def _dispatch_sources(
        self,
        *,
        query: str,
        source: LiteratureSource,
        limit: int,
        include_abstract: bool,
        abstract_max_chars: int,
    ) -> dict[str, JSONObject]:
        """Dispatch searches to all requested sources in parallel."""
        tasks = self._build_source_tasks(
            query=query,
            source=source,
            limit=limit,
            include_abstract=include_abstract,
            abstract_max_chars=abstract_max_chars,
        )

        async def _safe(
            name: str,
            coro: collections.abc.Awaitable[JSONObject],
        ) -> tuple[str, JSONObject]:
            try:
                res = await coro
                return (
                    name,
                    res if isinstance(res, dict) else {"error": "invalid_response"},
                )
            except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
                return (
                    name,
                    {
                        "query": query,
                        "source": name,
                        "results": [],
                        "citations": [],
                        "error": str(exc),
                    },
                )

        pairs = await asyncio.gather(*(_safe(name, coro) for name, coro in tasks))
        return dict(pairs)

    # ------------------------------------------------------------------
    # Deduplication and filtering
    # ------------------------------------------------------------------

    def _deduplicate_and_filter(
        self,
        *,
        by_source: dict[str, JSONObject],
        options: LiteratureOutputOptions,
        filters: LiteratureFilters,
    ) -> tuple[JSONArray, dict[str, JSONObject]]:
        """Merge, filter, and deduplicate results from all sources.

        Returns (filtered_results, citations_by_dedupe_key).
        """
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

                item_ctx = LiteratureItemContext(
                    title=title,
                    authors=list_str(authors) if authors is not None else None,
                    year=year,
                    doi=doi,
                    pmid=pmid,
                    journal=journal,
                )
                if not passes_filters(item_ctx, filters):
                    continue

                key = dedupe_key(item)
                if key in seen:
                    continue
                seen.add(key)

                authors_limited = limit_authors(
                    list_str(authors) if authors else None,
                    options.max_authors,
                )
                abstract_raw = item.get("abstract")
                abstract_value: str | None
                if options.include_abstract:
                    abstract_str = (
                        abstract_raw if isinstance(abstract_raw, str) else None
                    )
                    abstract_value = truncate_text(
                        abstract_str, options.abstract_max_chars
                    )
                else:
                    abstract_value = (
                        abstract_raw if isinstance(abstract_raw, str) else None
                    )
                filtered.append(
                    {
                        **item,
                        "source": src,
                        "authors": cast("JSONValue", authors_limited),
                        "abstract": abstract_value,
                    }
                )

                if isinstance(c, dict):
                    c2: JSONObject = {**c}
                    authors_raw = c2.get("authors")
                    if authors_raw is not None:
                        authors_list = list_str(authors_raw)
                        authors_limited = limit_authors(
                            authors_list, options.max_authors
                        )
                        c2["authors"] = cast("JSONValue", authors_limited)
                    citations_by_key[key] = c2

        return filtered, citations_by_key

    # ------------------------------------------------------------------
    # Sorting and reranking
    # ------------------------------------------------------------------

    def _sort_results(
        self,
        results: JSONArray,
        *,
        sort: LiteratureSort,
        source: LiteratureSource,
        query: str,
    ) -> JSONArray:
        """Sort (and optionally rerank) the filtered results."""

        def get_year_key(r: JSONValue) -> tuple[bool, int]:
            if not isinstance(r, dict):
                return (False, 0)
            year_raw = r.get("year")
            year = year_raw if isinstance(year_raw, int) else None
            return (year is not None, year if year is not None else 0)

        def get_score_key(r: JSONValue) -> tuple[bool, float]:
            if not isinstance(r, dict):
                return (False, 0.0)
            score_raw = r.get("score")
            score_val = score_raw if isinstance(score_raw, (int, float)) else None
            return (
                score_val is not None,
                float(score_val) if score_val is not None else 0.0,
            )

        if results and sort == "newest":
            return sorted(results, key=get_year_key, reverse=True)

        # Relevance reranking only for source="all"
        if results and sort == "relevance" and source == "all":
            scored: JSONArray = [
                {
                    **item,
                    "score": round(score, 2),
                    "scoreParts": cast("JSONValue", parts),
                }
                for item in results
                if isinstance(item, dict)
                for score, parts in [rerank_score(query, item)]
            ]
            return sorted(scored, key=get_score_key, reverse=True)

        return results

    # ------------------------------------------------------------------
    # Response assembly
    # ------------------------------------------------------------------

    def _build_response(
        self,
        *,
        query: str,
        source: LiteratureSource,
        sort: LiteratureSort,
        options: LiteratureOutputOptions,
        filters: LiteratureFilters,
        result_data: LiteratureResultData,
    ) -> JSONObject:
        """Assemble the final response payload."""
        sliced = result_data.results[: result_data.limit]

        def _ordered_citations(results_list: JSONArray) -> list[JSONObject]:
            ordered: list[JSONObject] = []
            for r in results_list:
                if not isinstance(r, dict):
                    continue
                key = dedupe_key(r)
                c = result_data.citations_by_key.get(key)
                if isinstance(c, dict):
                    ordered.append(c)
            return ordered

        citations = _ordered_citations(sliced)

        payload: JSONObject = {
            "query": query,
            "source": source,
            "sort": sort,
            "includeAbstract": options.include_abstract,
            "abstractMaxChars": options.abstract_max_chars,
            "maxAuthors": options.max_authors,
            "filters": {
                "yearFrom": filters.year_from,
                "yearTo": filters.year_to,
                "authorIncludes": filters.author_includes,
                "titleIncludes": filters.title_includes,
                "journalIncludes": filters.journal_includes,
                "doiEquals": filters.doi_equals,
                "pmidEquals": filters.pmid_equals,
                "requireDoi": filters.require_doi,
            },
            "results": sliced,
            "citations": cast("JSONValue", citations),
        }

        if source == "all":
            payload["bySource"] = cast("JSONValue", result_data.by_source)

        citations_raw = payload.get("citations")
        if isinstance(citations_raw, list):
            citations_list: list[JSONObject] = [
                c for c in citations_raw if isinstance(c, dict)
            ]
            ensure_unique_citation_tags(citations_list)

        return payload
