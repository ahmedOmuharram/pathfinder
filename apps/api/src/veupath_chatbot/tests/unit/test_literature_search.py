"""Unit tests for LiteratureSearchService and research utility functions.

Tests the full search() flow with mocked clients, plus standalone utility
function tests for dedupe_key, passes_filters, limit_authors, truncate_text,
and rerank_score.
"""

from dataclasses import dataclass, field
from typing import cast
from unittest.mock import AsyncMock

import pytest

from veupath_chatbot.domain.research.citations import (
    LiteratureFilters,
    LiteratureOutputOptions,
)
from veupath_chatbot.platform.types import JSONArray, JSONObject, JSONValue
from veupath_chatbot.services.research.literature_search import (
    LiteratureSearchService,
)
from veupath_chatbot.services.research.utils import (
    LiteratureItemContext,
    dedupe_key,
    limit_authors,
    passes_filters,
    rerank_score,
    truncate_text,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass
class _ResultSpec:
    title: str = "Paper"
    doi: str | None = "10.1234/test"
    pmid: str | None = None
    year: int | None = 2022
    authors: list[str] | None = field(default=None)
    abstract: str | None = None
    journal: str | None = None
    url: str | None = None


_DEFAULT_RESULT_SPEC = _ResultSpec()


def _result(spec: _ResultSpec = _DEFAULT_RESULT_SPEC) -> JSONObject:
    """Build a minimal result dict."""
    r: JSONObject = {"title": spec.title, "year": spec.year}
    if spec.doi is not None:
        r["doi"] = spec.doi
    if spec.pmid is not None:
        r["pmid"] = spec.pmid
    if spec.authors is not None:
        r["authors"] = cast("JSONValue", spec.authors)
    if spec.abstract is not None:
        r["abstract"] = spec.abstract
    if spec.journal is not None:
        r["journalTitle"] = spec.journal
    if spec.url is not None:
        r["url"] = spec.url
    return r


def _citation(
    *,
    title: str = "Paper",
    doi: str | None = "10.1234/test",
    authors: list[str] | None = None,
    tag: str = "ref",
) -> JSONObject:
    """Build a minimal citation dict."""
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


def _source_payload(
    results: JSONArray,
    citations: JSONArray | None = None,
    query: str = "test",
    source: str = "europepmc",
) -> JSONObject:
    """Build a standard client response payload."""
    if citations is None:
        citations = [
            _citation(title=str(r.get("title") if isinstance(r, dict) else ""))
            for r in results
        ]
    return {
        "query": query,
        "source": source,
        "results": results,
        "citations": citations,
    }


def _make_service() -> LiteratureSearchService:
    return LiteratureSearchService(timeout_seconds=1.0)


def _patch_client(
    service: LiteratureSearchService, attr: str, payload: JSONObject
) -> AsyncMock:
    """Create an AsyncMock for a client's search method and patch it."""
    mock = AsyncMock(return_value=payload)
    client = getattr(service, attr)
    client.search = mock
    return mock


# ---------------------------------------------------------------------------
# 1. Input validation: empty query returns error payload
# ---------------------------------------------------------------------------


class TestInputValidation:
    async def test_empty_query_returns_error(self) -> None:
        svc = _make_service()
        result = await svc.search("")
        assert result["error"] == "query_required"
        assert result["results"] == []
        assert result["citations"] == []

    async def test_whitespace_only_query_returns_error(self) -> None:
        svc = _make_service()
        result = await svc.search("   \t\n  ")
        assert result["error"] == "query_required"


# ---------------------------------------------------------------------------
# 2. Single source dispatch: source="europepmc" -> only 1 coroutine created
# ---------------------------------------------------------------------------


class TestSingleSourceDispatch:
    async def test_single_source_calls_only_that_client(self) -> None:
        svc = _make_service()
        payload = _source_payload(
            [_result(_ResultSpec(title="Malaria paper", doi="10.1/epmc"))],
            source="europepmc",
        )
        _patch_client(svc, "_europepmc", payload)
        crossref_mock = _patch_client(
            svc, "_crossref", _source_payload([], source="crossref")
        )

        result = await svc.search("malaria", source="europepmc")

        svc._europepmc.search.assert_called_once()
        crossref_mock.assert_not_called()
        assert isinstance(result["results"], list)
        results = result["results"]
        assert isinstance(results, list)
        assert len(results) == 1


# ---------------------------------------------------------------------------
# 3. All sources dispatch: source="all" -> 8 coroutines
# ---------------------------------------------------------------------------


class TestAllSourcesDispatch:
    async def test_all_dispatches_8_sources(self) -> None:
        svc = _make_service()
        empty = _source_payload([], source="any")
        _patch_client(svc, "_europepmc", empty)
        _patch_client(svc, "_crossref", empty)
        _patch_client(svc, "_openalex", empty)
        _patch_client(svc, "_semanticscholar", empty)
        _patch_client(svc, "_pubmed", empty)
        _patch_client(svc, "_arxiv", empty)
        _patch_client(svc, "_preprint", empty)

        result = await svc.search("malaria", source="all")

        svc._europepmc.search.assert_called_once()
        svc._crossref.search.assert_called_once()
        svc._openalex.search.assert_called_once()
        svc._semanticscholar.search.assert_called_once()
        svc._pubmed.search.assert_called_once()
        svc._arxiv.search.assert_called_once()
        # preprint.search called twice: biorxiv + medrxiv
        assert svc._preprint.search.call_count == 2
        assert "results" in result


# ---------------------------------------------------------------------------
# 4. Error tolerance: one provider raises -> others still return results
# ---------------------------------------------------------------------------


class TestErrorTolerance:
    async def test_one_provider_fails_others_succeed(self) -> None:
        svc = _make_service()
        good_payload = _source_payload(
            [_result(_ResultSpec(title="Good paper", doi="10.1/good"))],
            source="europepmc",
        )
        _patch_client(svc, "_europepmc", good_payload)
        svc._crossref.search = AsyncMock(side_effect=ValueError("timeout"))
        _patch_client(svc, "_openalex", _source_payload([], source="openalex"))
        _patch_client(
            svc, "_semanticscholar", _source_payload([], source="semanticscholar")
        )
        _patch_client(svc, "_pubmed", _source_payload([], source="pubmed"))
        _patch_client(svc, "_arxiv", _source_payload([], source="arxiv"))
        _patch_client(svc, "_preprint", _source_payload([], source="preprint"))

        result = await svc.search("malaria", source="all")

        results = result["results"]
        assert isinstance(results, list)
        assert len(results) >= 1
        # The failed source should appear in bySource with an error
        by_source = result.get("bySource")
        assert isinstance(by_source, dict)
        crossref_data = by_source.get("crossref")
        assert isinstance(crossref_data, dict)
        assert "error" in crossref_data


# ---------------------------------------------------------------------------
# 5. Deduplication: same DOI from 2 sources -> only 1 result
# ---------------------------------------------------------------------------


class TestDeduplicationByDoi:
    async def test_same_doi_deduped(self) -> None:
        svc = _make_service()
        shared_doi = "10.1234/shared"
        epmc_payload = _source_payload(
            [_result(_ResultSpec(title="Paper from EPMC", doi=shared_doi))],
            source="europepmc",
        )
        crossref_payload = _source_payload(
            [_result(_ResultSpec(title="Paper from Crossref", doi=shared_doi))],
            source="crossref",
        )
        _patch_client(svc, "_europepmc", epmc_payload)
        _patch_client(svc, "_crossref", crossref_payload)
        _patch_client(svc, "_openalex", _source_payload([], source="openalex"))
        _patch_client(
            svc, "_semanticscholar", _source_payload([], source="semanticscholar")
        )
        _patch_client(svc, "_pubmed", _source_payload([], source="pubmed"))
        _patch_client(svc, "_arxiv", _source_payload([], source="arxiv"))
        _patch_client(svc, "_preprint", _source_payload([], source="preprint"))

        result = await svc.search("malaria", source="all")

        results = result["results"]
        assert isinstance(results, list)
        assert len(results) == 1


# ---------------------------------------------------------------------------
# 6. Dedup by PMID: same PMID from different sources -> deduped
# ---------------------------------------------------------------------------


class TestDeduplicationByPmid:
    async def test_same_pmid_deduped(self) -> None:
        svc = _make_service()
        epmc_payload = _source_payload(
            [_result(_ResultSpec(title="From EPMC", doi=None, pmid="99999"))],
            source="europepmc",
        )
        pubmed_payload = _source_payload(
            [_result(_ResultSpec(title="From Pubmed", doi=None, pmid="99999"))],
            source="pubmed",
        )
        _patch_client(svc, "_europepmc", epmc_payload)
        _patch_client(svc, "_crossref", _source_payload([], source="crossref"))
        _patch_client(svc, "_openalex", _source_payload([], source="openalex"))
        _patch_client(
            svc, "_semanticscholar", _source_payload([], source="semanticscholar")
        )
        _patch_client(svc, "_pubmed", pubmed_payload)
        _patch_client(svc, "_arxiv", _source_payload([], source="arxiv"))
        _patch_client(svc, "_preprint", _source_payload([], source="preprint"))

        result = await svc.search("malaria", source="all")

        results = result["results"]
        assert isinstance(results, list)
        assert len(results) == 1


# ---------------------------------------------------------------------------
# 7. Year filtering: year_from=2020, year_to=2023 -> filters correctly
# ---------------------------------------------------------------------------


class TestYearFiltering:
    async def test_year_range_filters(self) -> None:
        svc = _make_service()
        payload = _source_payload(
            [
                _result(_ResultSpec(title="Old", doi="10.1/old", year=2018)),
                _result(_ResultSpec(title="In range", doi="10.1/ok", year=2021)),
                _result(_ResultSpec(title="Too new", doi="10.1/new", year=2025)),
            ],
            source="europepmc",
        )
        _patch_client(svc, "_europepmc", payload)

        result = await svc.search(
            "malaria",
            source="europepmc",
            filters=LiteratureFilters(year_from=2020, year_to=2023),
        )

        results = result["results"]
        assert isinstance(results, list)
        assert len(results) == 1
        assert isinstance(results[0], dict)
        assert results[0]["title"] == "In range"


# ---------------------------------------------------------------------------
# 8. Author filtering: author_includes="Smith" -> only matching results
# ---------------------------------------------------------------------------


class TestAuthorFiltering:
    async def test_author_includes_filters(self) -> None:
        svc = _make_service()
        payload = _source_payload(
            [
                _result(
                    _ResultSpec(
                        title="By Smith", doi="10.1/smith", authors=["John Smith"]
                    )
                ),
                _result(
                    _ResultSpec(
                        title="By Jones", doi="10.1/jones", authors=["Jane Jones"]
                    )
                ),
            ],
            source="europepmc",
        )
        _patch_client(svc, "_europepmc", payload)

        result = await svc.search(
            "malaria",
            source="europepmc",
            filters=LiteratureFilters(author_includes="Smith"),
        )

        results = result["results"]
        assert isinstance(results, list)
        assert len(results) == 1
        assert isinstance(results[0], dict)
        assert results[0]["title"] == "By Smith"


# ---------------------------------------------------------------------------
# 9. Title filtering: title_includes="malaria" -> only matching
# ---------------------------------------------------------------------------


class TestTitleFiltering:
    async def test_title_includes_filters(self) -> None:
        svc = _make_service()
        payload = _source_payload(
            [
                _result(_ResultSpec(title="Malaria vaccine trial", doi="10.1/m")),
                _result(_ResultSpec(title="Cancer treatment", doi="10.1/c")),
            ],
            source="europepmc",
        )
        _patch_client(svc, "_europepmc", payload)

        result = await svc.search(
            "vaccine",
            source="europepmc",
            filters=LiteratureFilters(title_includes="malaria"),
        )

        results = result["results"]
        assert isinstance(results, list)
        assert len(results) == 1
        assert isinstance(results[0], dict)
        assert "Malaria" in str(results[0]["title"])


# ---------------------------------------------------------------------------
# 10. DOI exact match: doi_equals -> exact match only
# ---------------------------------------------------------------------------


class TestDoiExactMatch:
    async def test_doi_equals_filters(self) -> None:
        svc = _make_service()
        target_doi = "10.1234/target"
        payload = _source_payload(
            [
                _result(_ResultSpec(title="Target", doi=target_doi)),
                _result(_ResultSpec(title="Other", doi="10.1234/other")),
            ],
            source="europepmc",
        )
        _patch_client(svc, "_europepmc", payload)

        result = await svc.search(
            "malaria",
            source="europepmc",
            filters=LiteratureFilters(doi_equals=target_doi),
        )

        results = result["results"]
        assert isinstance(results, list)
        assert len(results) == 1
        assert isinstance(results[0], dict)
        assert results[0]["doi"] == target_doi


# ---------------------------------------------------------------------------
# 11. require_doi: items without DOI filtered out
# ---------------------------------------------------------------------------


class TestRequireDoi:
    async def test_require_doi_filters_no_doi(self) -> None:
        svc = _make_service()
        payload = _source_payload(
            [
                _result(_ResultSpec(title="Has DOI", doi="10.1/yes")),
                _result(
                    _ResultSpec(title="No DOI", doi=None, url="http://example.com")
                ),
            ],
            source="europepmc",
        )
        _patch_client(svc, "_europepmc", payload)

        result = await svc.search(
            "malaria", source="europepmc", filters=LiteratureFilters(require_doi=True)
        )

        results = result["results"]
        assert isinstance(results, list)
        assert len(results) == 1
        assert isinstance(results[0], dict)
        assert results[0]["title"] == "Has DOI"


# ---------------------------------------------------------------------------
# 12. Sort by newest: results ordered by year descending
# ---------------------------------------------------------------------------


class TestSortByNewest:
    async def test_newest_sort_order(self) -> None:
        svc = _make_service()
        payload = _source_payload(
            [
                _result(_ResultSpec(title="Old", doi="10.1/a", year=2015)),
                _result(_ResultSpec(title="Newest", doi="10.1/b", year=2025)),
                _result(_ResultSpec(title="Mid", doi="10.1/c", year=2020)),
            ],
            source="europepmc",
        )
        _patch_client(svc, "_europepmc", payload)

        result = await svc.search("malaria", source="europepmc", sort="newest")

        results = result["results"]
        assert isinstance(results, list)
        assert len(results) == 3
        years = [r["year"] for r in results if isinstance(r, dict)]
        assert years == [2025, 2020, 2015]


# ---------------------------------------------------------------------------
# 13. Sort by relevance: results get rerank scores when source="all"
# ---------------------------------------------------------------------------


class TestSortByRelevance:
    async def test_relevance_adds_scores_for_all(self) -> None:
        svc = _make_service()
        payload = _source_payload(
            [
                _result(_ResultSpec(title="malaria vaccine efficacy", doi="10.1/a")),
                _result(_ResultSpec(title="unrelated topic", doi="10.1/b")),
            ],
            source="europepmc",
        )
        _patch_client(svc, "_europepmc", payload)
        _patch_client(svc, "_crossref", _source_payload([], source="crossref"))
        _patch_client(svc, "_openalex", _source_payload([], source="openalex"))
        _patch_client(
            svc, "_semanticscholar", _source_payload([], source="semanticscholar")
        )
        _patch_client(svc, "_pubmed", _source_payload([], source="pubmed"))
        _patch_client(svc, "_arxiv", _source_payload([], source="arxiv"))
        _patch_client(svc, "_preprint", _source_payload([], source="preprint"))

        result = await svc.search(
            "malaria vaccine",
            source="all",
            sort="relevance",
        )

        results = result["results"]
        assert isinstance(results, list)
        for item in results:
            assert isinstance(item, dict)
            assert "score" in item
            assert "scoreParts" in item

    async def test_relevance_no_scores_for_single_source(self) -> None:
        svc = _make_service()
        payload = _source_payload(
            [_result(_ResultSpec(title="Paper", doi="10.1/a"))],
            source="europepmc",
        )
        _patch_client(svc, "_europepmc", payload)

        result = await svc.search(
            "malaria",
            source="europepmc",
            sort="relevance",
        )

        results = result["results"]
        assert isinstance(results, list)
        assert len(results) == 1
        assert isinstance(results[0], dict)
        assert "score" not in results[0]


# ---------------------------------------------------------------------------
# 14. Limit: only returns first N results
# ---------------------------------------------------------------------------


class TestLimit:
    async def test_limit_caps_results(self) -> None:
        svc = _make_service()
        many_results = [
            _result(_ResultSpec(title=f"Paper {i}", doi=f"10.1/{i}")) for i in range(10)
        ]
        payload = _source_payload(many_results, source="europepmc")
        _patch_client(svc, "_europepmc", payload)

        result = await svc.search("malaria", source="europepmc", limit=3)

        results = result["results"]
        assert isinstance(results, list)
        assert len(results) == 3


# ---------------------------------------------------------------------------
# 15. Citation ordering: citations match result order
# ---------------------------------------------------------------------------


class TestCitationOrdering:
    async def test_citations_match_result_order(self) -> None:
        svc = _make_service()
        r1 = _result(_ResultSpec(title="First", doi="10.1/first"))
        r2 = _result(_ResultSpec(title="Second", doi="10.1/second"))
        c1 = _citation(title="First", doi="10.1/first")
        c2 = _citation(title="Second", doi="10.1/second")
        payload = _source_payload([r1, r2], citations=[c1, c2], source="europepmc")
        _patch_client(svc, "_europepmc", payload)

        result = await svc.search("malaria", source="europepmc")

        results = result["results"]
        citations = result["citations"]
        assert isinstance(results, list)
        assert isinstance(citations, list)
        assert len(citations) == len(results)
        # Each citation should correspond to the result at the same index
        for i, r in enumerate(results):
            assert isinstance(r, dict)
            assert isinstance(citations[i], dict)
            # Both should share the same DOI
            assert r.get("doi") == citations[i].get("doi")


# ---------------------------------------------------------------------------
# 16. Author limiting: max_authors=2 -> truncated with "et al."
# ---------------------------------------------------------------------------


class TestAuthorLimiting:
    async def test_authors_truncated_in_results(self) -> None:
        svc = _make_service()
        payload = _source_payload(
            [
                _result(
                    _ResultSpec(
                        title="Multi-author",
                        doi="10.1/multi",
                        authors=["Alice", "Bob", "Carol", "Dave"],
                    )
                ),
            ],
            source="europepmc",
        )
        _patch_client(svc, "_europepmc", payload)

        result = await svc.search(
            "malaria",
            source="europepmc",
            options=LiteratureOutputOptions(max_authors=2),
        )

        results = result["results"]
        assert isinstance(results, list)
        assert len(results) == 1
        item = results[0]
        assert isinstance(item, dict)
        authors = item["authors"]
        assert isinstance(authors, list)
        assert len(authors) == 3  # 2 + "et al."
        assert authors[0] == "Alice"
        assert authors[1] == "Bob"
        assert authors[2] == "et al."


# ---------------------------------------------------------------------------
# 17. Abstract truncation: include_abstract=True with long abstracts
# ---------------------------------------------------------------------------


class TestAbstractTruncation:
    async def test_long_abstract_truncated(self) -> None:
        svc = _make_service()
        long_abstract = "A" * 5000
        payload = _source_payload(
            [
                _result(
                    _ResultSpec(title="Paper", doi="10.1/abs", abstract=long_abstract)
                )
            ],
            source="europepmc",
        )
        _patch_client(svc, "_europepmc", payload)

        result = await svc.search(
            "malaria",
            source="europepmc",
            options=LiteratureOutputOptions(
                include_abstract=True, abstract_max_chars=500
            ),
        )

        results = result["results"]
        assert isinstance(results, list)
        assert len(results) == 1
        item = results[0]
        assert isinstance(item, dict)
        abstract = item.get("abstract")
        assert isinstance(abstract, str)
        assert len(abstract) <= 500

    async def test_short_abstract_not_truncated(self) -> None:
        svc = _make_service()
        short_abstract = "This is a short abstract."
        payload = _source_payload(
            [
                _result(
                    _ResultSpec(
                        title="Paper", doi="10.1/short", abstract=short_abstract
                    )
                )
            ],
            source="europepmc",
        )
        _patch_client(svc, "_europepmc", payload)

        result = await svc.search(
            "malaria",
            source="europepmc",
            options=LiteratureOutputOptions(
                include_abstract=True, abstract_max_chars=2000
            ),
        )

        results = result["results"]
        assert isinstance(results, list)
        item = results[0]
        assert isinstance(item, dict)
        assert item.get("abstract") == short_abstract


# ===========================================================================
# Utility function tests (services/research/utils.py)
# ===========================================================================


# ---------------------------------------------------------------------------
# dedupe_key
# ---------------------------------------------------------------------------


class TestDedupeKey:
    def test_pmid_takes_priority(self) -> None:
        item: JSONObject = {
            "pmid": "12345",
            "doi": "10.1/x",
            "url": "http://example.com",
            "title": "A Paper",
            "year": 2020,
        }
        assert dedupe_key(item) == "pmid:12345"

    def test_doi_if_no_pmid(self) -> None:
        item: JSONObject = {
            "doi": "10.1234/ABC",
            "url": "http://example.com",
            "title": "A Paper",
            "year": 2020,
        }
        assert dedupe_key(item) == "doi:10.1234/abc"

    def test_url_if_no_pmid_or_doi(self) -> None:
        item: JSONObject = {
            "url": "http://example.com/paper",
            "title": "A Paper",
            "year": 2020,
        }
        assert dedupe_key(item) == "url:http://example.com/paper"

    def test_title_year_fallback(self) -> None:
        item: JSONObject = {"title": "My Paper", "year": 2022}
        key = dedupe_key(item)
        assert key.startswith("title:")
        assert "my paper" in key
        assert "2022" in key

    def test_empty_pmid_falls_through(self) -> None:
        item: JSONObject = {"pmid": "  ", "doi": "10.1/x", "title": "P", "year": 2020}
        assert dedupe_key(item) == "doi:10.1/x"


# ---------------------------------------------------------------------------
# passes_filters
# ---------------------------------------------------------------------------


class TestPassesFilters:
    def test_no_filters_passes(self) -> None:
        assert passes_filters(
            LiteratureItemContext(
                title="Paper",
                authors=None,
                year=2022,
                doi="10.1/x",
                pmid=None,
                journal=None,
            ),
            LiteratureFilters(
                year_from=None,
                year_to=None,
                author_includes=None,
                title_includes=None,
                journal_includes=None,
                doi_equals=None,
                pmid_equals=None,
                require_doi=False,
            ),
        )

    def test_year_from_rejects_old(self) -> None:
        assert not passes_filters(
            LiteratureItemContext(
                title="Old", authors=None, year=2010, doi=None, pmid=None, journal=None
            ),
            LiteratureFilters(
                year_from=2015,
                year_to=None,
                author_includes=None,
                title_includes=None,
                journal_includes=None,
                doi_equals=None,
                pmid_equals=None,
                require_doi=False,
            ),
        )

    def test_year_to_rejects_new(self) -> None:
        assert not passes_filters(
            LiteratureItemContext(
                title="New", authors=None, year=2025, doi=None, pmid=None, journal=None
            ),
            LiteratureFilters(
                year_from=None,
                year_to=2023,
                author_includes=None,
                title_includes=None,
                journal_includes=None,
                doi_equals=None,
                pmid_equals=None,
                require_doi=False,
            ),
        )

    def test_year_none_rejected_by_year_from(self) -> None:
        assert not passes_filters(
            LiteratureItemContext(
                title="No year",
                authors=None,
                year=None,
                doi=None,
                pmid=None,
                journal=None,
            ),
            LiteratureFilters(
                year_from=2020,
                year_to=None,
                author_includes=None,
                title_includes=None,
                journal_includes=None,
                doi_equals=None,
                pmid_equals=None,
                require_doi=False,
            ),
        )

    def test_require_doi_rejects_none(self) -> None:
        assert not passes_filters(
            LiteratureItemContext(
                title="No DOI",
                authors=None,
                year=2022,
                doi=None,
                pmid=None,
                journal=None,
            ),
            LiteratureFilters(
                year_from=None,
                year_to=None,
                author_includes=None,
                title_includes=None,
                journal_includes=None,
                doi_equals=None,
                pmid_equals=None,
                require_doi=True,
            ),
        )

    def test_doi_equals_exact(self) -> None:
        assert passes_filters(
            LiteratureItemContext(
                title="X",
                authors=None,
                year=2022,
                doi="10.1/match",
                pmid=None,
                journal=None,
            ),
            LiteratureFilters(
                year_from=None,
                year_to=None,
                author_includes=None,
                title_includes=None,
                journal_includes=None,
                doi_equals="10.1/match",
                pmid_equals=None,
                require_doi=False,
            ),
        )

    def test_doi_equals_case_insensitive(self) -> None:
        assert passes_filters(
            LiteratureItemContext(
                title="X",
                authors=None,
                year=2022,
                doi="10.1/MATCH",
                pmid=None,
                journal=None,
            ),
            LiteratureFilters(
                year_from=None,
                year_to=None,
                author_includes=None,
                title_includes=None,
                journal_includes=None,
                doi_equals="10.1/match",
                pmid_equals=None,
                require_doi=False,
            ),
        )

    def test_doi_equals_rejects_mismatch(self) -> None:
        assert not passes_filters(
            LiteratureItemContext(
                title="X",
                authors=None,
                year=2022,
                doi="10.1/other",
                pmid=None,
                journal=None,
            ),
            LiteratureFilters(
                year_from=None,
                year_to=None,
                author_includes=None,
                title_includes=None,
                journal_includes=None,
                doi_equals="10.1/match",
                pmid_equals=None,
                require_doi=False,
            ),
        )

    def test_pmid_equals(self) -> None:
        assert passes_filters(
            LiteratureItemContext(
                title="X", authors=None, year=2022, doi=None, pmid="12345", journal=None
            ),
            LiteratureFilters(
                year_from=None,
                year_to=None,
                author_includes=None,
                title_includes=None,
                journal_includes=None,
                doi_equals=None,
                pmid_equals="12345",
                require_doi=False,
            ),
        )

    def test_title_includes_case_insensitive(self) -> None:
        assert passes_filters(
            LiteratureItemContext(
                title="Malaria Vaccine Trial",
                authors=None,
                year=2022,
                doi=None,
                pmid=None,
                journal=None,
            ),
            LiteratureFilters(
                year_from=None,
                year_to=None,
                author_includes=None,
                title_includes="malaria",
                journal_includes=None,
                doi_equals=None,
                pmid_equals=None,
                require_doi=False,
            ),
        )

    def test_journal_includes(self) -> None:
        assert passes_filters(
            LiteratureItemContext(
                title="Paper",
                authors=None,
                year=2022,
                doi=None,
                pmid=None,
                journal="Nature Medicine",
            ),
            LiteratureFilters(
                year_from=None,
                year_to=None,
                author_includes=None,
                title_includes=None,
                journal_includes="nature",
                doi_equals=None,
                pmid_equals=None,
                require_doi=False,
            ),
        )

    def test_author_includes_substring(self) -> None:
        assert passes_filters(
            LiteratureItemContext(
                title="Paper",
                authors=["John Smith", "Jane Doe"],
                year=2022,
                doi=None,
                pmid=None,
                journal=None,
            ),
            LiteratureFilters(
                year_from=None,
                year_to=None,
                author_includes="Smith",
                title_includes=None,
                journal_includes=None,
                doi_equals=None,
                pmid_equals=None,
                require_doi=False,
            ),
        )

    def test_author_includes_no_match(self) -> None:
        assert not passes_filters(
            LiteratureItemContext(
                title="Paper",
                authors=["John Smith"],
                year=2022,
                doi=None,
                pmid=None,
                journal=None,
            ),
            LiteratureFilters(
                year_from=None,
                year_to=None,
                author_includes="Jones",
                title_includes=None,
                journal_includes=None,
                doi_equals=None,
                pmid_equals=None,
                require_doi=False,
            ),
        )


# ---------------------------------------------------------------------------
# limit_authors
# ---------------------------------------------------------------------------


class TestLimitAuthors:
    def test_none_returns_none(self) -> None:
        assert limit_authors(None, 2) is None

    def test_empty_list_returns_none(self) -> None:
        assert limit_authors([], 2) is None

    def test_within_limit_returns_all(self) -> None:
        result = limit_authors(["Alice", "Bob"], 3)
        assert result == ["Alice", "Bob"]

    def test_over_limit_truncates_with_et_al(self) -> None:
        result = limit_authors(["Alice", "Bob", "Carol", "Dave"], 2)
        assert result is not None
        assert len(result) == 3
        assert result == ["Alice", "Bob", "et al."]

    def test_exactly_at_limit(self) -> None:
        result = limit_authors(["Alice", "Bob"], 2)
        assert result == ["Alice", "Bob"]

    def test_max_authors_negative_one_no_limit(self) -> None:
        authors = ["A", "B", "C", "D", "E"]
        result = limit_authors(authors, -1)
        assert result == authors

    def test_max_authors_zero_just_et_al(self) -> None:
        result = limit_authors(["Alice", "Bob"], 0)
        assert result == ["et al."]


# ---------------------------------------------------------------------------
# truncate_text
# ---------------------------------------------------------------------------


class TestTruncateText:
    def test_none_returns_none(self) -> None:
        assert truncate_text(None, 100) is None

    def test_empty_returns_none(self) -> None:
        assert truncate_text("", 100) is None

    def test_whitespace_only_returns_none(self) -> None:
        assert truncate_text("   ", 100) is None

    def test_short_text_unchanged(self) -> None:
        assert truncate_text("Hello world", 100) == "Hello world"

    def test_exactly_at_limit(self) -> None:
        text = "A" * 50
        assert truncate_text(text, 50) == text

    def test_over_limit_truncated_with_ellipsis(self) -> None:
        text = "A" * 100
        result = truncate_text(text, 50)
        assert result is not None
        assert len(result) <= 50
        assert result.endswith("\u2026")  # ellipsis character


# ---------------------------------------------------------------------------
# rerank_score
# ---------------------------------------------------------------------------


class TestRerankScore:
    def test_perfect_match_high_score(self) -> None:
        item: JSONObject = {
            "title": "malaria vaccine",
            "abstract": "malaria vaccine study",
        }
        score, parts = rerank_score("malaria vaccine", item)
        assert score > 50.0
        assert "title" in parts
        assert "abstract" in parts
        assert "journal" in parts

    def test_no_match_low_score(self) -> None:
        item: JSONObject = {
            "title": "quantum physics",
            "abstract": "quantum entanglement",
        }
        score, _ = rerank_score("malaria vaccine", item)
        # Should be a low score for completely unrelated content
        assert score < 50.0

    def test_empty_fields_zero_score(self) -> None:
        item: JSONObject = {"title": "", "abstract": ""}
        _score, parts = rerank_score("malaria", item)
        assert parts["title"] == 0.0
        assert parts["abstract"] == 0.0

    def test_score_weights(self) -> None:
        # Title has 0.70 weight, abstract 0.28, journal 0.02
        item: JSONObject = {
            "title": "malaria vaccine",
            "abstract": "",
            "journalTitle": "",
        }
        score, parts = rerank_score("malaria vaccine", item)
        # Score should be driven by title match
        assert score == pytest.approx(
            0.70 * parts["title"] + 0.28 * parts["abstract"] + 0.02 * parts["journal"],
            abs=0.1,
        )


# ===========================================================================
# Integration-style tests: full search() with combined filters
# ===========================================================================


class TestSearchCombinedFilters:
    async def test_year_and_author_combined(self) -> None:
        svc = _make_service()
        payload = _source_payload(
            [
                _result(
                    _ResultSpec(title="P1", doi="10.1/p1", year=2021, authors=["Smith"])
                ),
                _result(
                    _ResultSpec(title="P2", doi="10.1/p2", year=2018, authors=["Smith"])
                ),
                _result(
                    _ResultSpec(title="P3", doi="10.1/p3", year=2021, authors=["Jones"])
                ),
            ],
            source="europepmc",
        )
        _patch_client(svc, "_europepmc", payload)

        result = await svc.search(
            "test",
            source="europepmc",
            filters=LiteratureFilters(year_from=2020, author_includes="Smith"),
        )

        results = result["results"]
        assert isinstance(results, list)
        assert len(results) == 1
        assert isinstance(results[0], dict)
        assert results[0]["title"] == "P1"

    async def test_response_includes_filters_metadata(self) -> None:
        svc = _make_service()
        payload = _source_payload(
            [_result(_ResultSpec(title="Paper", doi="10.1/x"))],
            source="europepmc",
        )
        _patch_client(svc, "_europepmc", payload)

        result = await svc.search(
            "malaria",
            source="europepmc",
            filters=LiteratureFilters(year_from=2020, year_to=2024, require_doi=True),
        )

        filters = result.get("filters")
        assert isinstance(filters, dict)
        assert filters["yearFrom"] == 2020
        assert filters["yearTo"] == 2024
        assert filters["requireDoi"] is True

    async def test_by_source_only_in_all_mode(self) -> None:
        svc = _make_service()
        payload = _source_payload([], source="europepmc")
        _patch_client(svc, "_europepmc", payload)

        result = await svc.search("malaria", source="europepmc")
        assert "bySource" not in result

    async def test_by_source_present_in_all_mode(self) -> None:
        svc = _make_service()
        empty = _source_payload([], source="any")
        _patch_client(svc, "_europepmc", empty)
        _patch_client(svc, "_crossref", empty)
        _patch_client(svc, "_openalex", empty)
        _patch_client(svc, "_semanticscholar", empty)
        _patch_client(svc, "_pubmed", empty)
        _patch_client(svc, "_arxiv", empty)
        _patch_client(svc, "_preprint", empty)

        result = await svc.search("malaria", source="all")
        assert "bySource" in result
