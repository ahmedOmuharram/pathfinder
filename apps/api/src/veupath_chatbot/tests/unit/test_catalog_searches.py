"""Unit tests for services/catalog/searches.py.

Covers list_searches(), search_for_searches(), _search_for_searches_via_site_search(),
find_record_type_for_search(), and the term_variants helper.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from veupath_chatbot.domain.search import SearchContext
from veupath_chatbot.integrations.veupathdb.site_search_client import (
    SiteSearchDocument,
    SiteSearchResponse,
    SiteSearchResults,
)
from veupath_chatbot.integrations.veupathdb.wdk_models import WDKSearch
from veupath_chatbot.platform.errors import WDKError
from veupath_chatbot.services.catalog.searches import (
    _search_for_searches_via_site_search,
    find_record_type_for_search,
    list_searches,
    search_for_searches,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_wdk_searches(dicts: list[Any]) -> list[WDKSearch]:
    """Convert raw dicts to WDKSearch objects, skipping non-dicts."""
    result: list[WDKSearch] = []
    for d in dicts:
        if isinstance(d, dict):
            # WDKSearch requires urlSegment; fall back to "name" key.
            entry = {**d, "urlSegment": d["name"]} if "urlSegment" not in d and "name" in d else d
            result.append(WDKSearch.model_validate(entry))
    return result


def _mock_discovery(
    record_types: list[Any] | None = None,
    searches_by_rt: dict[str, list[Any]] | None = None,
) -> MagicMock:
    """Build a mock discovery service."""
    discovery = MagicMock()
    discovery.get_record_types = AsyncMock(return_value=record_types or [])
    if searches_by_rt is not None:
        parsed: dict[str, list[WDKSearch]] = {
            rt: _to_wdk_searches(raw) for rt, raw in searches_by_rt.items()
        }
        discovery.get_searches = AsyncMock(
            side_effect=lambda _site_id, rt: parsed.get(rt, [])
        )
    else:
        discovery.get_searches = AsyncMock(return_value=[])
    return discovery


def _mock_client(
    record_types: list[Any] | None = None,
    searches_by_rt: dict[str, list[Any]] | None = None,
) -> MagicMock:
    """Build a mock VEuPathDBClient."""
    client = MagicMock()
    client.get_record_types = AsyncMock(return_value=record_types or [])
    if searches_by_rt is not None:
        parsed: dict[str, list[WDKSearch]] = {
            rt: _to_wdk_searches(raw) for rt, raw in searches_by_rt.items()
        }
        client.get_searches = AsyncMock(
            side_effect=lambda rt: parsed.get(rt, [])
        )
    else:
        client.get_searches = AsyncMock(return_value=[])
    return client


# ---------------------------------------------------------------------------
# list_searches
# ---------------------------------------------------------------------------


class TestListSearches:
    """Test the list_searches() function."""

    async def test_basic_list(self) -> None:
        discovery = _mock_discovery(
            searches_by_rt={
                "gene": [
                    {
                        "urlSegment": "GenesByTaxon",
                        "name": "GenesByTaxonQuestion",
                        "displayName": "Genes by Taxon",
                        "description": "Find genes by organism",
                    },
                ]
            }
        )
        with patch(
            "veupath_chatbot.services.catalog.searches.get_discovery_service",
            return_value=discovery,
        ):
            result = await list_searches("plasmodb", "gene")

        assert len(result) == 1
        assert result[0]["name"] == "GenesByTaxon"
        assert result[0]["displayName"] == "Genes by Taxon"

    async def test_prefers_url_segment_over_name(self) -> None:
        discovery = _mock_discovery(
            searches_by_rt={
                "gene": [
                    {"urlSegment": "GenesByTaxon", "name": "GenesByTaxonQ"},
                ]
            }
        )
        with patch(
            "veupath_chatbot.services.catalog.searches.get_discovery_service",
            return_value=discovery,
        ):
            result = await list_searches("plasmodb", "gene")

        assert result[0]["name"] == "GenesByTaxon"

    async def test_falls_back_to_name_when_no_url_segment(self) -> None:
        discovery = _mock_discovery(
            searches_by_rt={
                "gene": [{"name": "GenesByTaxonQ"}],
            }
        )
        with patch(
            "veupath_chatbot.services.catalog.searches.get_discovery_service",
            return_value=discovery,
        ):
            result = await list_searches("plasmodb", "gene")

        assert result[0]["name"] == "GenesByTaxonQ"

    async def test_filters_internal_searches(self) -> None:
        discovery = _mock_discovery(
            searches_by_rt={
                "gene": [
                    {
                        "urlSegment": "GenesByTaxon",
                        "displayName": "Genes by Taxon",
                        "fullName": "GeneQuestions.GenesByTaxon",
                    },
                    {
                        "urlSegment": "InternalSearch",
                        "displayName": "Internal",
                        "fullName": "InternalQuestions.InternalSearch",
                    },
                ]
            }
        )
        with patch(
            "veupath_chatbot.services.catalog.searches.get_discovery_service",
            return_value=discovery,
        ):
            result = await list_searches("plasmodb", "gene")

        assert len(result) == 1
        assert result[0]["name"] == "GenesByTaxon"

    async def test_skips_non_dict_entries(self) -> None:
        discovery = _mock_discovery(
            searches_by_rt={
                "gene": [
                    "not_a_dict",
                    None,
                    {"urlSegment": "GenesByTaxon"},
                ]
            }
        )
        with patch(
            "veupath_chatbot.services.catalog.searches.get_discovery_service",
            return_value=discovery,
        ):
            result = await list_searches("plasmodb", "gene")

        assert len(result) == 1

    async def test_empty_list(self) -> None:
        discovery = _mock_discovery(searches_by_rt={"gene": []})
        with patch(
            "veupath_chatbot.services.catalog.searches.get_discovery_service",
            return_value=discovery,
        ):
            result = await list_searches("plasmodb", "gene")

        assert result == []

    async def test_missing_optional_fields_default_to_empty(self) -> None:
        discovery = _mock_discovery(
            searches_by_rt={
                "gene": [{"urlSegment": "GenesByTaxon"}],
            }
        )
        with patch(
            "veupath_chatbot.services.catalog.searches.get_discovery_service",
            return_value=discovery,
        ):
            result = await list_searches("plasmodb", "gene")

        assert result[0]["displayName"] == ""


# ---------------------------------------------------------------------------
# _search_for_searches_via_site_search
# ---------------------------------------------------------------------------


def _make_site_search_response(docs: list[SiteSearchDocument]) -> SiteSearchResponse:
    """Build a SiteSearchResponse from a list of SiteSearchDocument objects."""
    return SiteSearchResponse(
        search_results=SiteSearchResults(total_count=len(docs), documents=docs)
    )


def _mock_site_router(response: SiteSearchResponse) -> MagicMock:
    """Build a mock site router whose site-search client returns *response*."""
    router = MagicMock()
    search_client = MagicMock()
    search_client.search = AsyncMock(return_value=response)
    router.get_site_search_client = MagicMock(return_value=search_client)
    return router


def _mock_site_router_raising(exc: Exception) -> MagicMock:
    """Build a mock site router whose site-search client raises *exc*."""
    router = MagicMock()
    search_client = MagicMock()
    search_client.search = AsyncMock(side_effect=exc)
    router.get_site_search_client = MagicMock(return_value=search_client)
    return router


class TestSearchForSearchesViaSiteSearch:
    """Test the _search_for_searches_via_site_search() function."""

    async def test_basic_site_search_result(self) -> None:
        doc = SiteSearchDocument(
            primary_key=["GenesByTaxon", "gene"],
            hyperlink_name="Genes by Taxon",
            found_in_fields={
                "TEXT__search_description": ["Find genes by taxonomy"],
            },
        )
        router = _mock_site_router(_make_site_search_response([doc]))
        with patch(
            "veupath_chatbot.services.catalog.searches.get_site_router",
            return_value=router,
        ):
            result = await _search_for_searches_via_site_search("plasmodb", "taxon")

        assert len(result) == 1
        assert result[0]["name"] == "GenesByTaxon"
        assert result[0]["displayName"] == "Genes by Taxon"
        assert result[0]["recordType"] == "gene"
        assert result[0]["description"] == "Find genes by taxonomy"

    async def test_returns_empty_on_exception(self) -> None:
        router = _mock_site_router_raising(WDKError(detail="Network error"))
        with patch(
            "veupath_chatbot.services.catalog.searches.get_site_router",
            return_value=router,
        ):
            result = await _search_for_searches_via_site_search("plasmodb", "taxon")

        assert result == []

    async def test_skips_bad_primary_keys(self) -> None:
        docs = [
            SiteSearchDocument(primary_key=["onlyone"]),  # too short
            SiteSearchDocument(primary_key=["", "gene"]),  # empty search name
            SiteSearchDocument(primary_key=["GenesByTaxon", ""]),  # empty record type
            SiteSearchDocument(primary_key=["ValidSearch", "gene"], hyperlink_name="Valid"),
        ]
        router = _mock_site_router(_make_site_search_response(docs))
        with patch(
            "veupath_chatbot.services.catalog.searches.get_site_router",
            return_value=router,
        ):
            result = await _search_for_searches_via_site_search("plasmodb", "test")

        assert len(result) == 1
        assert result[0]["name"] == "ValidSearch"

    async def test_respects_limit(self) -> None:
        docs = [
            SiteSearchDocument(
                primary_key=[f"Search{i}", "gene"],
                hyperlink_name=f"Search {i}",
            )
            for i in range(10)
        ]
        router = _mock_site_router(_make_site_search_response(docs))
        with patch(
            "veupath_chatbot.services.catalog.searches.get_site_router",
            return_value=router,
        ):
            result = await _search_for_searches_via_site_search(
                "plasmodb", "search", limit=3
            )

        assert len(result) == 3

    async def test_display_name_falls_back_to_found_in_fields(self) -> None:
        doc = SiteSearchDocument(
            primary_key=["GenesByTaxon", "gene"],
            hyperlink_name="",
            found_in_fields={
                "TEXT__search_displayName": ["<em>Genes</em> by Taxon"],
            },
        )
        router = _mock_site_router(_make_site_search_response([doc]))
        with patch(
            "veupath_chatbot.services.catalog.searches.get_site_router",
            return_value=router,
        ):
            result = await _search_for_searches_via_site_search("plasmodb", "taxon")

        # HTML tags should be stripped
        assert result[0]["displayName"] == "Genes by Taxon"

    async def test_display_name_falls_back_to_search_name(self) -> None:
        doc = SiteSearchDocument(
            primary_key=["GenesByTaxon", "gene"],
            hyperlink_name="",
            found_in_fields={},
        )
        router = _mock_site_router(_make_site_search_response([doc]))
        with patch(
            "veupath_chatbot.services.catalog.searches.get_site_router",
            return_value=router,
        ):
            result = await _search_for_searches_via_site_search("plasmodb", "taxon")

        assert result[0]["displayName"] == "GenesByTaxon"


# ---------------------------------------------------------------------------
# search_for_searches
# ---------------------------------------------------------------------------


class TestSearchForSearches:
    """Test the search_for_searches() function."""

    async def test_uses_site_search_when_no_record_type(self) -> None:
        """When record_type is None, discovery candidates are scored and
        site-search results provide a supplementary boost."""
        discovery = _mock_discovery(
            record_types=[{"urlSegment": "gene", "name": "Genes"}],
            searches_by_rt={
                "gene": [
                    {
                        "urlSegment": "GenesByTaxon",
                        "displayName": "Genes by Taxon",
                        "description": "Find genes by taxon",
                        "name": "GenesByTaxonQ",
                    }
                ],
            },
        )
        with (
            patch(
                "veupath_chatbot.services.catalog.searches._search_for_searches_via_site_search",
                new_callable=AsyncMock,
                return_value=[
                    {
                        "name": "GenesByTaxon",
                        "displayName": "Genes by Taxon",
                        "description": "",
                        "recordType": "gene",
                    }
                ],
            ),
            patch(
                "veupath_chatbot.services.catalog.searches.get_discovery_service",
                return_value=discovery,
            ),
        ):
            result = await search_for_searches("plasmodb", None, "taxon")

        assert len(result) == 1
        assert result[0]["name"] == "GenesByTaxon"

    async def test_falls_back_to_discovery_when_site_search_empty(self) -> None:
        discovery = _mock_discovery(
            record_types=[{"urlSegment": "gene", "name": "Genes"}],
            searches_by_rt={
                "gene": [
                    {
                        "urlSegment": "GenesByTaxon",
                        "displayName": "Genes by Taxon",
                        "description": "Find genes",
                        "name": "GenesByTaxonQ",
                    },
                ]
            },
        )
        with (
            patch(
                "veupath_chatbot.services.catalog.searches._search_for_searches_via_site_search",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "veupath_chatbot.services.catalog.searches.get_discovery_service",
                return_value=discovery,
            ),
        ):
            result = await search_for_searches("plasmodb", None, "taxon")

        assert len(result) == 1
        assert result[0]["name"] == "GenesByTaxon"

    async def test_filters_by_single_record_type(self) -> None:
        discovery = _mock_discovery(
            searches_by_rt={
                "gene": [
                    {
                        "urlSegment": "GenesByTaxon",
                        "displayName": "Genes by Taxon",
                        "description": "desc",
                        "name": "Q",
                    },
                ]
            }
        )
        with patch(
            "veupath_chatbot.services.catalog.searches.get_discovery_service",
            return_value=discovery,
        ):
            result = await search_for_searches("plasmodb", "gene", "taxon")

        assert len(result) == 1

    async def test_filters_by_record_type_list(self) -> None:
        discovery = _mock_discovery(
            searches_by_rt={
                "gene": [
                    {
                        "urlSegment": "GenesByTaxon",
                        "displayName": "Genes by Taxon",
                        "description": "desc",
                        "name": "Q",
                    },
                ],
                "transcript": [
                    {
                        "urlSegment": "TranscriptsByTaxon",
                        "displayName": "Transcripts by Taxon",
                        "description": "desc",
                        "name": "Q2",
                    },
                ],
            }
        )
        with patch(
            "veupath_chatbot.services.catalog.searches.get_discovery_service",
            return_value=discovery,
        ):
            result = await search_for_searches(
                "plasmodb", ["gene", "transcript"], "taxon"
            )

        assert len(result) == 2
        names = {r["name"] for r in result}
        assert names == {"GenesByTaxon", "TranscriptsByTaxon"}

    async def test_deduplicates_record_type_list(self) -> None:
        discovery = _mock_discovery(
            searches_by_rt={
                "gene": [
                    {
                        "urlSegment": "GenesByTaxon",
                        "displayName": "Genes by Taxon",
                        "description": "desc",
                        "name": "Q",
                    },
                ],
            }
        )
        with patch(
            "veupath_chatbot.services.catalog.searches.get_discovery_service",
            return_value=discovery,
        ):
            result = await search_for_searches("plasmodb", ["gene", "gene"], "taxon")

        # Should not produce duplicate results
        assert len(result) == 1

    async def test_skips_internal_searches(self) -> None:
        discovery = _mock_discovery(
            searches_by_rt={
                "gene": [
                    {
                        "urlSegment": "GenesByTaxon",
                        "displayName": "Genes by Taxon",
                        "description": "desc",
                        "isInternal": False,
                    },
                    {
                        "urlSegment": "InternalSearch",
                        "displayName": "Internal",
                        "description": "internal",
                        "isInternal": True,
                    },
                ]
            }
        )
        with patch(
            "veupath_chatbot.services.catalog.searches.get_discovery_service",
            return_value=discovery,
        ):
            result = await search_for_searches("plasmodb", "gene", "taxon")

        names = [r["name"] for r in result]
        assert "InternalSearch" not in names

    async def test_scores_and_sorts_by_relevance(self) -> None:
        """Searches with more matching terms should rank higher."""
        discovery = _mock_discovery(
            searches_by_rt={
                "gene": [
                    {
                        "urlSegment": "GenesByLocation",
                        "displayName": "Location Search",
                        "description": "Location only",
                        "name": "Q1",
                    },
                    {
                        "urlSegment": "GenesByTaxon",
                        "displayName": "Genes by Taxon",
                        "description": "Find genes by taxon classification",
                        "name": "GenesByTaxonQ",
                    },
                ]
            }
        )
        with patch(
            "veupath_chatbot.services.catalog.searches.get_discovery_service",
            return_value=discovery,
        ):
            result = await search_for_searches("plasmodb", "gene", "genes taxon")

        # GenesByTaxon should rank first (matches both terms)
        assert result[0]["name"] == "GenesByTaxon"

    async def test_no_suffix_stripping(self) -> None:
        """Scoring uses raw substring matching — no suffix stemming."""
        discovery = _mock_discovery(
            searches_by_rt={
                "gene": [
                    {
                        "urlSegment": "GeneByOrganism",
                        "displayName": "Gene by Organism",
                        "description": "",
                        "name": "Q",
                    },
                ]
            }
        )
        with patch(
            "veupath_chatbot.services.catalog.searches.get_discovery_service",
            return_value=discovery,
        ):
            # "genes" does NOT match "gene" (no suffix stripping)
            result = await search_for_searches("plasmodb", "gene", "genes")

        assert len(result) == 0

    async def test_limits_results_to_20(self) -> None:
        searches = [
            {
                "urlSegment": f"Search{i}",
                "displayName": f"Search {i} keyword",
                "description": "",
                "name": f"Q{i}",
            }
            for i in range(30)
        ]
        discovery = _mock_discovery(searches_by_rt={"gene": searches})
        with patch(
            "veupath_chatbot.services.catalog.searches.get_discovery_service",
            return_value=discovery,
        ):
            result = await search_for_searches("plasmodb", "gene", "keyword")

        assert len(result) <= 20

    async def test_no_matches_returns_empty(self) -> None:
        discovery = _mock_discovery(
            searches_by_rt={
                "gene": [
                    {
                        "urlSegment": "GenesByTaxon",
                        "displayName": "Genes by Taxon",
                        "description": "",
                        "name": "Q",
                    },
                ]
            }
        )
        with patch(
            "veupath_chatbot.services.catalog.searches.get_discovery_service",
            return_value=discovery,
        ):
            result = await search_for_searches("plasmodb", "gene", "zzzznonexistent")

        assert result == []

    async def test_empty_query_matches_on_full_string(self) -> None:
        """Empty query should not match anything (no terms, no query_lower)."""
        discovery = _mock_discovery(
            searches_by_rt={
                "gene": [
                    {
                        "urlSegment": "GenesByTaxon",
                        "displayName": "Genes",
                        "description": "",
                        "name": "Q",
                    },
                ]
            }
        )
        with patch(
            "veupath_chatbot.services.catalog.searches.get_discovery_service",
            return_value=discovery,
        ):
            result = await search_for_searches("plasmodb", "gene", "")

        # Empty query has no terms, so nothing matches
        assert result == []

    async def test_result_does_not_contain_score(self) -> None:
        """Score is used internally but should not appear in output."""
        discovery = _mock_discovery(
            searches_by_rt={
                "gene": [
                    {
                        "urlSegment": "GenesByTaxon",
                        "displayName": "Genes by Taxon",
                        "description": "desc",
                        "name": "Q",
                    },
                ]
            }
        )
        with patch(
            "veupath_chatbot.services.catalog.searches.get_discovery_service",
            return_value=discovery,
        ):
            result = await search_for_searches("plasmodb", "gene", "taxon")

        for r in result:
            assert "score" not in r


# ---------------------------------------------------------------------------
# find_record_type_for_search
# ---------------------------------------------------------------------------


class TestResolveRecordTypeForSearch:
    """Test the find_record_type_for_search() function.

    The implementation delegates to SearchCatalog.find_record_type_for_search()
    (a synchronous in-memory lookup on pre-cached data) and falls back to the
    caller-supplied *record_type* when the catalog returns None.
    """

    def _patch_catalog(self, resolved: str | None) -> Any:
        """Return a context manager that patches get_discovery_service.

        The mock DiscoveryService.get_catalog() returns a mock SearchCatalog
        whose find_record_type_for_search() returns *resolved*.
        """
        catalog = MagicMock()
        catalog.find_record_type_for_search = MagicMock(return_value=resolved)
        discovery = MagicMock()
        discovery.get_catalog = AsyncMock(return_value=catalog)
        return patch(
            "veupath_chatbot.services.catalog.searches.get_discovery_service",
            return_value=discovery,
        )

    async def test_returns_resolved_type_when_found(self) -> None:
        with self._patch_catalog("transcript"):
            result = await find_record_type_for_search(
                SearchContext("plasmodb", "gene", "TranscriptsByTaxon")
            )
        assert result == "transcript"

    async def test_returns_same_type_when_search_belongs_to_it(self) -> None:
        with self._patch_catalog("gene"):
            result = await find_record_type_for_search(
                SearchContext("plasmodb", "gene", "GenesByTaxon")
            )
        assert result == "gene"

    async def test_falls_back_to_record_type_when_not_found(self) -> None:
        with self._patch_catalog(None):
            result = await find_record_type_for_search(
                SearchContext("plasmodb", "gene", "NonexistentSearch")
            )
        assert result == "gene"

    async def test_falls_back_to_record_type_on_empty_string(self) -> None:
        with self._patch_catalog(""):
            result = await find_record_type_for_search(SearchContext("plasmodb", "gene", "SomeSearch"))
        assert result == "gene"

    async def test_passes_site_id_to_get_catalog(self) -> None:
        catalog = MagicMock()
        catalog.find_record_type_for_search = MagicMock(return_value="gene")
        discovery = MagicMock()
        discovery.get_catalog = AsyncMock(return_value=catalog)
        with patch(
            "veupath_chatbot.services.catalog.searches.get_discovery_service",
            return_value=discovery,
        ):
            await find_record_type_for_search(SearchContext("toxodb", "gene", "GenesByTaxon"))
        discovery.get_catalog.assert_awaited_once_with("toxodb")

    async def test_passes_search_name_to_catalog(self) -> None:
        catalog = MagicMock()
        catalog.find_record_type_for_search = MagicMock(return_value="gene")
        discovery = MagicMock()
        discovery.get_catalog = AsyncMock(return_value=catalog)
        with patch(
            "veupath_chatbot.services.catalog.searches.get_discovery_service",
            return_value=discovery,
        ):
            await find_record_type_for_search(SearchContext("plasmodb", "gene", "GenesByTaxon"))
        catalog.find_record_type_for_search.assert_called_once_with("GenesByTaxon")
