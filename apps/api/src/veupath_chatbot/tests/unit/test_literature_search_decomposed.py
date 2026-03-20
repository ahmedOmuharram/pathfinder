"""Tests for decomposed LiteratureSearchService helper methods."""

import asyncio
from typing import cast

import pytest

from veupath_chatbot.domain.research.citations import LiteratureSource
from veupath_chatbot.platform.types import JSONArray, JSONObject, JSONValue
from veupath_chatbot.services.research.literature_search import (
    LiteratureSearchService,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def service() -> LiteratureSearchService:
    return LiteratureSearchService(timeout_seconds=5.0)


def _make_result(
    *,
    title: str = "A Paper",
    doi: str | None = "10.1234/test",
    pmid: str | None = None,
    year: int | None = 2020,
    authors: list[str] | None = None,
    abstract: str | None = None,
    journal: str | None = None,
    source: str | None = None,
    url: str | None = None,
) -> JSONObject:
    r: JSONObject = {"title": title, "year": year}
    if doi is not None:
        r["doi"] = doi
    if pmid is not None:
        r["pmid"] = pmid
    if authors is not None:
        r["authors"] = cast("JSONValue", authors)
    if abstract is not None:
        r["abstract"] = abstract
    if journal is not None:
        r["journalTitle"] = journal
    if source is not None:
        r["source"] = source
    if url is not None:
        r["url"] = url
    return r


def _make_citation(
    *,
    title: str = "A Paper",
    doi: str | None = "10.1234/test",
    authors: list[str] | None = None,
    tag: str = "ref",
) -> JSONObject:
    c: JSONObject = {
        "id": "cit_1",
        "source": "europepmc",
        "tag": tag,
        "title": title,
    }
    if doi is not None:
        c["doi"] = doi
    if authors is not None:
        c["authors"] = cast("JSONValue", authors)
    return c


def _make_source_payload(
    results: JSONArray,
    citations: JSONArray | None = None,
) -> JSONObject:
    if citations is None:
        citations = [
            _make_citation(title=str(r.get("title") if isinstance(r, dict) else ""))
            for r in results
        ]
    return {"results": results, "citations": citations}


# ---------------------------------------------------------------------------
# _validate_inputs
# ---------------------------------------------------------------------------


class TestValidateInputs:
    def test_empty_query_returns_error(self, service: LiteratureSearchService) -> None:
        result = service._validate_inputs(
            "", limit=5, abstract_max_chars=2000, max_authors=2
        )
        assert result is not None
        assert result["error"] == "query_required"

    def test_whitespace_query_returns_error(
        self, service: LiteratureSearchService
    ) -> None:
        result = service._validate_inputs(
            "   ", limit=5, abstract_max_chars=2000, max_authors=2
        )
        assert result is not None

    def test_valid_query_returns_none(self, service: LiteratureSearchService) -> None:
        result = service._validate_inputs(
            "malaria", limit=5, abstract_max_chars=2000, max_authors=2
        )
        assert result is None

    def test_limit_clamped_to_range(self, service: LiteratureSearchService) -> None:
        # The method should return None (valid), and we test clamping via search params
        assert (
            service._validate_inputs(
                "q", limit=0, abstract_max_chars=2000, max_authors=2
            )
            is None
        )
        assert (
            service._validate_inputs(
                "q", limit=100, abstract_max_chars=2000, max_authors=2
            )
            is None
        )


# ---------------------------------------------------------------------------
# _build_source_tasks
# ---------------------------------------------------------------------------


class TestBuildSourceTasks:
    def test_all_source_returns_8_tasks(self, service: LiteratureSearchService) -> None:
        tasks = service._build_source_tasks(
            query="malaria",
            source="all",
            limit=5,
            include_abstract=False,
            abstract_max_chars=2000,
        )
        try:
            assert len(tasks) == 8
            names = [name for name, _ in tasks]
            assert "europepmc" in names
            assert "crossref" in names
            assert "openalex" in names
            assert "semanticscholar" in names
            assert "pubmed" in names
            assert "arxiv" in names
            assert "biorxiv" in names
            assert "medrxiv" in names
        finally:
            for _, coro in tasks:
                if asyncio.iscoroutine(coro):
                    coro.close()

    def test_single_source_returns_1_task(
        self, service: LiteratureSearchService
    ) -> None:
        sources: list[LiteratureSource] = [
            "europepmc",
            "crossref",
            "openalex",
            "semanticscholar",
            "pubmed",
            "arxiv",
            "biorxiv",
            "medrxiv",
        ]
        for src in sources:
            tasks = service._build_source_tasks(
                query="test",
                source=src,
                limit=5,
                include_abstract=False,
                abstract_max_chars=2000,
            )
            try:
                assert len(tasks) == 1
                assert tasks[0][0] == src
            finally:
                for _, coro in tasks:
                    if asyncio.iscoroutine(coro):
                        coro.close()


# ---------------------------------------------------------------------------
# _deduplicate_and_filter
# ---------------------------------------------------------------------------


class TestDeduplicateAndFilter:
    def test_removes_duplicates_by_doi(self, service: LiteratureSearchService) -> None:
        r1 = _make_result(title="Paper A", doi="10.1234/same")
        r2 = _make_result(title="Paper B", doi="10.1234/same")
        c1 = _make_citation(title="Paper A", doi="10.1234/same")
        c2 = _make_citation(title="Paper B", doi="10.1234/same")
        by_source: dict[str, JSONObject] = {
            "europepmc": _make_source_payload([r1], [c1]),
            "crossref": _make_source_payload([r2], [c2]),
        }
        filtered, _citations_by_key = service._deduplicate_and_filter(
            by_source=by_source,
            include_abstract=False,
            abstract_max_chars=2000,
            max_authors=2,
            year_from=None,
            year_to=None,
            author_includes=None,
            title_includes=None,
            journal_includes=None,
            doi_equals=None,
            pmid_equals=None,
            require_doi=False,
        )
        assert len(filtered) == 1

    def test_removes_duplicates_by_pmid(self, service: LiteratureSearchService) -> None:
        r1 = _make_result(title="Paper A", doi=None, pmid="12345")
        r2 = _make_result(title="Paper B", doi=None, pmid="12345")
        by_source: dict[str, JSONObject] = {
            "europepmc": _make_source_payload([r1]),
            "pubmed": _make_source_payload([r2]),
        }
        filtered, _ = service._deduplicate_and_filter(
            by_source=by_source,
            include_abstract=False,
            abstract_max_chars=2000,
            max_authors=2,
            year_from=None,
            year_to=None,
            author_includes=None,
            title_includes=None,
            journal_includes=None,
            doi_equals=None,
            pmid_equals=None,
            require_doi=False,
        )
        assert len(filtered) == 1

    def test_keeps_unique_items(self, service: LiteratureSearchService) -> None:
        r1 = _make_result(title="Paper A", doi="10.1234/a")
        r2 = _make_result(title="Paper B", doi="10.1234/b")
        by_source: dict[str, JSONObject] = {
            "europepmc": _make_source_payload([r1, r2]),
        }
        filtered, _ = service._deduplicate_and_filter(
            by_source=by_source,
            include_abstract=False,
            abstract_max_chars=2000,
            max_authors=2,
            year_from=None,
            year_to=None,
            author_includes=None,
            title_includes=None,
            journal_includes=None,
            doi_equals=None,
            pmid_equals=None,
            require_doi=False,
        )
        assert len(filtered) == 2

    def test_applies_year_filter(self, service: LiteratureSearchService) -> None:
        r1 = _make_result(title="Old", doi="10.1234/old", year=2010)
        r2 = _make_result(title="New", doi="10.1234/new", year=2022)
        by_source: dict[str, JSONObject] = {
            "europepmc": _make_source_payload([r1, r2]),
        }
        filtered, _ = service._deduplicate_and_filter(
            by_source=by_source,
            include_abstract=False,
            abstract_max_chars=2000,
            max_authors=2,
            year_from=2015,
            year_to=None,
            author_includes=None,
            title_includes=None,
            journal_includes=None,
            doi_equals=None,
            pmid_equals=None,
            require_doi=False,
        )
        assert len(filtered) == 1
        assert isinstance(filtered[0], dict)
        assert filtered[0].get("title") == "New"

    def test_applies_require_doi(self, service: LiteratureSearchService) -> None:
        r1 = _make_result(title="Has DOI", doi="10.1234/a")
        r2 = _make_result(title="No DOI", doi=None)
        by_source: dict[str, JSONObject] = {
            "europepmc": _make_source_payload([r1, r2]),
        }
        filtered, _ = service._deduplicate_and_filter(
            by_source=by_source,
            include_abstract=False,
            abstract_max_chars=2000,
            max_authors=2,
            year_from=None,
            year_to=None,
            author_includes=None,
            title_includes=None,
            journal_includes=None,
            doi_equals=None,
            pmid_equals=None,
            require_doi=True,
        )
        assert len(filtered) == 1
        assert isinstance(filtered[0], dict)
        assert filtered[0].get("doi") == "10.1234/a"

    def test_limits_authors(self, service: LiteratureSearchService) -> None:
        r1 = _make_result(
            title="Many Authors",
            doi="10.1234/many",
            authors=["Alice", "Bob", "Carol", "Dave"],
        )
        by_source: dict[str, JSONObject] = {
            "europepmc": _make_source_payload([r1]),
        }
        filtered, _ = service._deduplicate_and_filter(
            by_source=by_source,
            include_abstract=False,
            abstract_max_chars=2000,
            max_authors=2,
            year_from=None,
            year_to=None,
            author_includes=None,
            title_includes=None,
            journal_includes=None,
            doi_equals=None,
            pmid_equals=None,
            require_doi=False,
        )
        assert len(filtered) == 1
        item = filtered[0]
        assert isinstance(item, dict)
        authors = item.get("authors")
        assert isinstance(authors, list)
        # 2 authors + "et al."
        assert len(authors) == 3
        assert authors[-1] == "et al."

    def test_citations_by_key_populated(self, service: LiteratureSearchService) -> None:
        r1 = _make_result(title="Paper A", doi="10.1234/a")
        c1 = _make_citation(title="Paper A", doi="10.1234/a")
        by_source: dict[str, JSONObject] = {
            "europepmc": _make_source_payload([r1], [c1]),
        }
        _filtered, citations_by_key = service._deduplicate_and_filter(
            by_source=by_source,
            include_abstract=False,
            abstract_max_chars=2000,
            max_authors=2,
            year_from=None,
            year_to=None,
            author_includes=None,
            title_includes=None,
            journal_includes=None,
            doi_equals=None,
            pmid_equals=None,
            require_doi=False,
        )
        assert len(citations_by_key) == 1

    def test_skips_invalid_source_payloads(
        self, service: LiteratureSearchService
    ) -> None:
        by_source: dict[str, JSONObject] = {
            "europepmc": {"error": "timeout"},
        }
        filtered, citations_by_key = service._deduplicate_and_filter(
            by_source=by_source,
            include_abstract=False,
            abstract_max_chars=2000,
            max_authors=2,
            year_from=None,
            year_to=None,
            author_includes=None,
            title_includes=None,
            journal_includes=None,
            doi_equals=None,
            pmid_equals=None,
            require_doi=False,
        )
        assert len(filtered) == 0
        assert len(citations_by_key) == 0


# ---------------------------------------------------------------------------
# _sort_results
# ---------------------------------------------------------------------------


class TestSortResults:
    def test_newest_sort(self, service: LiteratureSearchService) -> None:
        items: JSONArray = [
            _make_result(title="Old", year=2015, doi="10.1/a"),
            _make_result(title="New", year=2023, doi="10.1/b"),
            _make_result(title="Mid", year=2019, doi="10.1/c"),
        ]
        sorted_items = service._sort_results(
            items, sort="newest", source="europepmc", query="test"
        )
        assert isinstance(sorted_items[0], dict)
        assert sorted_items[0].get("year") == 2023
        assert isinstance(sorted_items[1], dict)
        assert sorted_items[1].get("year") == 2019
        assert isinstance(sorted_items[2], dict)
        assert sorted_items[2].get("year") == 2015

    def test_relevance_sort_all_adds_scores(
        self, service: LiteratureSearchService
    ) -> None:
        items: JSONArray = [
            _make_result(title="malaria vaccine", doi="10.1/a"),
            _make_result(title="unrelated topic", doi="10.1/b"),
        ]
        sorted_items = service._sort_results(
            items, sort="relevance", source="all", query="malaria vaccine"
        )
        # All items should have score keys
        for item in sorted_items:
            assert isinstance(item, dict)
            assert "score" in item
            assert "scoreParts" in item

    def test_relevance_single_source_no_scores(
        self, service: LiteratureSearchService
    ) -> None:
        items: JSONArray = [
            _make_result(title="Paper A", doi="10.1/a"),
        ]
        sorted_items = service._sort_results(
            items, sort="relevance", source="europepmc", query="test"
        )
        assert isinstance(sorted_items[0], dict)
        assert "score" not in sorted_items[0]

    def test_empty_list(self, service: LiteratureSearchService) -> None:
        sorted_items = service._sort_results(
            [], sort="newest", source="all", query="test"
        )
        assert sorted_items == []


# ---------------------------------------------------------------------------
# _build_response
# ---------------------------------------------------------------------------


class TestBuildResponse:
    def test_response_structure(self, service: LiteratureSearchService) -> None:
        results: JSONArray = [_make_result(title="Paper A", doi="10.1234/a")]
        citations_by_key = {
            "doi:10.1234/a": _make_citation(title="Paper A", doi="10.1234/a")
        }
        payload = service._build_response(
            query="test",
            source="europepmc",
            sort="relevance",
            include_abstract=False,
            abstract_max_chars=2000,
            max_authors=2,
            year_from=None,
            year_to=None,
            author_includes=None,
            title_includes=None,
            journal_includes=None,
            doi_equals=None,
            pmid_equals=None,
            require_doi=False,
            results=results,
            citations_by_key=citations_by_key,
            by_source={},
            limit=5,
        )
        assert payload["query"] == "test"
        assert payload["source"] == "europepmc"
        assert payload["sort"] == "relevance"
        assert isinstance(payload["results"], list)
        assert isinstance(payload["citations"], list)
        assert isinstance(payload["filters"], dict)

    def test_citations_aligned_with_results(
        self, service: LiteratureSearchService
    ) -> None:
        r1 = _make_result(title="A", doi="10.1234/a")
        r2 = _make_result(title="B", doi="10.1234/b")
        c1 = _make_citation(title="A", doi="10.1234/a")
        c2 = _make_citation(title="B", doi="10.1234/b")
        citations_by_key = {
            "doi:10.1234/a": c1,
            "doi:10.1234/b": c2,
        }
        payload = service._build_response(
            query="test",
            source="europepmc",
            sort="relevance",
            include_abstract=False,
            abstract_max_chars=2000,
            max_authors=2,
            year_from=None,
            year_to=None,
            author_includes=None,
            title_includes=None,
            journal_includes=None,
            doi_equals=None,
            pmid_equals=None,
            require_doi=False,
            results=[r1, r2],
            citations_by_key=citations_by_key,
            by_source={},
            limit=5,
        )
        results_out = payload["results"]
        citations_out = payload["citations"]
        assert isinstance(results_out, list)
        assert isinstance(citations_out, list)
        assert len(citations_out) == len(results_out)

    def test_limit_applied_to_results(self, service: LiteratureSearchService) -> None:
        results: JSONArray = [
            _make_result(title=f"Paper {i}", doi=f"10.1234/{i}") for i in range(10)
        ]
        citations_by_key = {
            f"doi:10.1234/{i}": _make_citation(title=f"Paper {i}", doi=f"10.1234/{i}")
            for i in range(10)
        }
        payload = service._build_response(
            query="test",
            source="europepmc",
            sort="relevance",
            include_abstract=False,
            abstract_max_chars=2000,
            max_authors=2,
            year_from=None,
            year_to=None,
            author_includes=None,
            title_includes=None,
            journal_includes=None,
            doi_equals=None,
            pmid_equals=None,
            require_doi=False,
            results=results,
            citations_by_key=citations_by_key,
            by_source={},
            limit=3,
        )
        results_out = payload["results"]
        citations_out = payload["citations"]
        assert isinstance(results_out, list)
        assert isinstance(citations_out, list)
        assert len(results_out) == 3
        assert len(citations_out) == 3

    def test_by_source_included_for_all(self, service: LiteratureSearchService) -> None:
        by_source: dict[str, JSONObject] = {
            "europepmc": {"results": [], "citations": []}
        }
        payload = service._build_response(
            query="test",
            source="all",
            sort="relevance",
            include_abstract=False,
            abstract_max_chars=2000,
            max_authors=2,
            year_from=None,
            year_to=None,
            author_includes=None,
            title_includes=None,
            journal_includes=None,
            doi_equals=None,
            pmid_equals=None,
            require_doi=False,
            results=[],
            citations_by_key={},
            by_source=by_source,
            limit=5,
        )
        assert "bySource" in payload

    def test_by_source_excluded_for_single(
        self, service: LiteratureSearchService
    ) -> None:
        payload = service._build_response(
            query="test",
            source="europepmc",
            sort="relevance",
            include_abstract=False,
            abstract_max_chars=2000,
            max_authors=2,
            year_from=None,
            year_to=None,
            author_includes=None,
            title_includes=None,
            journal_includes=None,
            doi_equals=None,
            pmid_equals=None,
            require_doi=False,
            results=[],
            citations_by_key={},
            by_source={},
            limit=5,
        )
        assert "bySource" not in payload
