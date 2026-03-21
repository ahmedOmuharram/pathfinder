"""Tests for wdk_catalog.py (ingest orchestration) and wdk_fetch.py.

Covers:
  - fetch_record_types_and_searches with various WDK response shapes
  - fetch_search_details with summary data already present vs needing fetch
  - ingest_site pipeline orchestration
  - Edge cases: malformed record types, empty searches, dict-wrapped responses
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

from veupath_chatbot.domain.parameters.specs import unwrap_search_data
from veupath_chatbot.integrations.vectorstore.ingest.wdk_fetch import (
    fetch_record_types_and_searches,
    fetch_search_details,
)
from veupath_chatbot.integrations.veupathdb.wdk_models import WDKSearch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_client(
    record_types: list[Any] | None = None,
    searches_by_rt: dict[str, list[Any]] | None = None,
    search_details: dict[str, Any] | None = None,
) -> MagicMock:
    client = MagicMock()
    client.base_url = "https://plasmodb.org/plasmo/service"
    client.get_record_types = AsyncMock(return_value=record_types or [])
    if searches_by_rt is not None:
        client.get_searches = AsyncMock(
            side_effect=lambda rt: [
                WDKSearch.model_validate(s) if isinstance(s, dict) else s
                for s in searches_by_rt.get(rt, [])
            ]
        )
    else:
        client.get_searches = AsyncMock(return_value=[])
    client.get_search_details = AsyncMock(return_value=search_details or {})
    return client


# ---------------------------------------------------------------------------
# fetch_record_types_and_searches
# ---------------------------------------------------------------------------


class TestFetchRecordTypesAndSearches:
    """Test the fetch_record_types_and_searches function."""

    async def test_basic_expanded_record_types(self) -> None:
        """Standard WDK expanded response with inline searches."""
        client = _mock_client(
            record_types=[
                {
                    "urlSegment": "gene",
                    "name": "GeneRecordClass",
                    "searches": [
                        {"urlSegment": "GenesByTaxon", "displayName": "Genes by Taxon"},
                    ],
                },
            ]
        )
        record_types, searches = await fetch_record_types_and_searches(client)

        assert len(record_types) == 1
        assert len(searches) == 1
        rt_name, s = searches[0]
        assert rt_name == "gene"
        assert s["urlSegment"] == "GenesByTaxon"

    async def test_dict_wrapped_response(self) -> None:
        """WDK sometimes wraps record types in a dict with 'recordTypes' key."""
        client = _mock_client(
            record_types={
                "recordTypes": [
                    {"urlSegment": "gene", "searches": []},
                ]
            }
        )
        record_types, _searches = await fetch_record_types_and_searches(client)
        assert len(record_types) == 1

    async def test_dict_wrapped_with_records_key(self) -> None:
        client = _mock_client(
            record_types={"records": [{"urlSegment": "gene", "searches": []}]}
        )
        record_types, _ = await fetch_record_types_and_searches(client)
        assert len(record_types) == 1

    async def test_dict_wrapped_with_result_key(self) -> None:
        client = _mock_client(
            record_types={"result": [{"urlSegment": "gene", "searches": []}]}
        )
        record_types, _ = await fetch_record_types_and_searches(client)
        assert len(record_types) == 1

    async def test_string_record_types(self) -> None:
        """Record types can be plain strings (just names)."""
        client = _mock_client(record_types=["gene", "transcript"])
        record_types, _ = await fetch_record_types_and_searches(client)
        assert len(record_types) == 2

    async def test_fetches_searches_when_not_inline(self) -> None:
        """When record type dict has no 'searches' key, fetches them separately."""
        client = _mock_client(
            record_types=[{"urlSegment": "gene"}],
            searches_by_rt={
                "gene": [{"urlSegment": "GenesByTaxon"}],
            },
        )
        _record_types, searches = await fetch_record_types_and_searches(client)
        assert len(searches) == 1

    async def test_skips_non_dict_non_str_entries(self) -> None:
        client = _mock_client(record_types=[42, None, True, {"urlSegment": "gene"}])
        record_types, _ = await fetch_record_types_and_searches(client)
        assert len(record_types) == 1

    async def test_skips_record_type_without_name(self) -> None:
        client = _mock_client(record_types=[{"urlSegment": "", "name": ""}])
        record_types, _ = await fetch_record_types_and_searches(client)
        assert len(record_types) == 0

    async def test_skips_non_dict_search_entries(self) -> None:
        client = _mock_client(
            record_types=[
                {
                    "urlSegment": "gene",
                    "searches": ["not-a-dict", 42, {"urlSegment": "Valid"}],
                }
            ]
        )
        _, searches = await fetch_record_types_and_searches(client)
        assert len(searches) == 1
        assert searches[0][1]["urlSegment"] == "Valid"

    async def test_get_searches_exception_handled(self) -> None:
        """If get_searches fails, should continue without crashing."""
        client = MagicMock()
        client.get_record_types = AsyncMock(return_value=[{"urlSegment": "gene"}])
        client.get_searches = AsyncMock(side_effect=RuntimeError("network error"))
        record_types, searches = await fetch_record_types_and_searches(client)
        assert len(record_types) == 1
        assert len(searches) == 0

    async def test_non_list_searches_value_treated_as_empty(self) -> None:
        """If 'searches' key is not a list, should treat as empty."""
        client = _mock_client(
            record_types=[{"urlSegment": "gene", "searches": "not-a-list"}],
            searches_by_rt={"gene": []},
        )
        _, searches = await fetch_record_types_and_searches(client)
        assert len(searches) == 0

    async def test_empty_record_types(self) -> None:
        client = _mock_client(record_types=[])
        record_types, searches = await fetch_record_types_and_searches(client)
        assert len(record_types) == 0
        assert len(searches) == 0

    async def test_none_record_types(self) -> None:
        """get_record_types returning None should be handled gracefully."""
        client = MagicMock()
        client.get_record_types = AsyncMock(return_value=None)
        record_types, searches = await fetch_record_types_and_searches(client)
        assert len(record_types) == 0
        assert len(searches) == 0


# ---------------------------------------------------------------------------
# fetch_search_details
# ---------------------------------------------------------------------------


class TestFetchSearchDetails:
    """Test the fetch_search_details function."""

    async def test_uses_summary_when_parameters_present(self) -> None:
        """If summary already has parameters, no fetch is needed."""
        summary_unwrapped = {
            "searchName": "GenesByTaxon",
            "parameters": [{"name": "organism"}],
        }
        client = _mock_client()

        details, error = await fetch_search_details(
            client, "gene", "GenesByTaxon", summary_unwrapped
        )

        assert error is None
        assert details is summary_unwrapped
        client.get_search_details.assert_not_called()

    async def test_uses_summary_when_param_specs_present(self) -> None:
        summary_unwrapped = {
            "searchName": "GenesByTaxon",
            "paramSpecs": [{"name": "organism"}],
        }
        client = _mock_client()

        details, error = await fetch_search_details(
            client, "gene", "GenesByTaxon", summary_unwrapped
        )

        assert error is None
        assert details is summary_unwrapped

    async def test_uses_summary_when_empty_param_names(self) -> None:
        """Searches with empty paramNames list need no further fetch."""
        summary_unwrapped = {
            "searchName": "AllGenes",
            "paramNames": [],
        }
        client = _mock_client()

        details, error = await fetch_search_details(
            client, "gene", "AllGenes", summary_unwrapped
        )

        assert error is None
        assert details is summary_unwrapped

    async def test_fetches_details_when_no_params_in_summary(self) -> None:
        summary_unwrapped = {"searchName": "GenesByTaxon"}
        details_response = {
            "displayName": "Genes by Taxon",
            "parameters": [{"name": "organism"}],
        }
        client = _mock_client(search_details=details_response)

        _details, error = await fetch_search_details(
            client, "gene", "GenesByTaxon", summary_unwrapped
        )

        assert error is None
        client.get_search_details.assert_called_once()

    async def test_returns_error_on_fetch_failure(self) -> None:
        summary_unwrapped = {"searchName": "GenesByTaxon"}
        client = MagicMock()
        client.get_search_details = AsyncMock(
            side_effect=RuntimeError("Connection refused")
        )

        details, error = await fetch_search_details(
            client, "gene", "GenesByTaxon", summary_unwrapped
        )

        assert error is not None
        assert "Connection refused" in error
        assert details == {}

    async def test_search_data_in_details_is_unwrapped(self) -> None:
        """The searchData envelope from WDK should be unwrapped."""
        summary_unwrapped = {"searchName": "GenesByTaxon"}
        details_response = {
            "searchData": {
                "displayName": "Genes by Taxon",
                "parameters": [{"name": "organism"}],
            }
        }
        client = _mock_client(search_details=details_response)

        details, error = await fetch_search_details(
            client, "gene", "GenesByTaxon", summary_unwrapped
        )

        assert error is None
        # The details should be unwrapped from searchData
        assert details.get("displayName") == "Genes by Taxon"

    async def test_has_param_defs_from_search_data(self) -> None:
        """Parameters nested inside searchData should still be detected."""
        summary_unwrapped = {
            "searchName": "GenesByTaxon",
            "searchData": {
                "parameters": [{"name": "organism"}],
            },
        }
        client = _mock_client()

        _details, error = await fetch_search_details(
            client, "gene", "GenesByTaxon", summary_unwrapped
        )

        assert error is None
        # Should recognize that param defs exist and not fetch


# ---------------------------------------------------------------------------
# unwrap_search_data
# ---------------------------------------------------------------------------


class TestUnwrapSearchData:
    """Test the canonical unwrap_search_data from param_resolution."""

    def test_none_returns_none(self) -> None:
        assert unwrap_search_data(None) is None

    def test_dict_without_search_data(self) -> None:
        d = {"displayName": "Test"}
        assert unwrap_search_data(d) == d

    def test_dict_with_search_data(self) -> None:
        inner = {"displayName": "Inner"}
        d = {"searchData": inner}
        assert unwrap_search_data(d) == inner

    def test_non_dict_search_data_returns_outer(self) -> None:
        d = {"searchData": "not-a-dict"}
        assert unwrap_search_data(d) == d
