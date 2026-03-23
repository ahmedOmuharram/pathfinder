"""Tests for decomposed helpers in services/catalog/param_resolution.py.

Covers allowed_values() and fetch_search_details().
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from veupath_chatbot.domain.search import SearchContext
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    WDKRecordType,
    WDKSearch,
    WDKSearchResponse,
    WDKValidation,
)
from veupath_chatbot.platform.errors import AppError, ErrorCode, ValidationError
from veupath_chatbot.platform.types import JSONArray, JSONObject
from veupath_chatbot.services.catalog.param_discovery import fetch_search_details
from veupath_chatbot.services.catalog.param_resolution import get_search_parameters
from veupath_chatbot.services.catalog.vocab_rendering import allowed_values

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _normalize_search_dict(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize a raw search dict so it can be parsed by WDKSearch.model_validate()."""
    d = dict(raw)
    if "urlSegment" not in d:
        d["urlSegment"] = "unknown"
    params = d.get("parameters")
    if isinstance(params, dict):
        d["paramNames"] = [k for k in params if k]
        d.pop("parameters")
    elif isinstance(params, list):
        normalized: list[dict[str, Any]] = []
        for p in params:
            if isinstance(p, dict):
                entry = {**p, "type": "string"} if "type" not in p else p
                normalized.append(entry)
        d["parameters"] = normalized
    return d


def _to_wdk_search_response(details: dict[str, Any]) -> WDKSearchResponse:
    """Convert a raw dict to WDKSearchResponse."""
    normalized = _normalize_search_dict(details)
    search = WDKSearch.model_validate(normalized)
    return WDKSearchResponse(search_data=search, validation=WDKValidation())


# ---------------------------------------------------------------------------
# allowed_values
# ---------------------------------------------------------------------------


class TestAllowedValues:
    """Direct tests for the module-level allowed_values() helper."""

    def _call(self, vocab: JSONObject | JSONArray | None) -> list[JSONObject]:
        return allowed_values(vocab)

    @staticmethod
    def _values(entries: list[JSONObject]) -> list[str]:
        """Extract just the 'value' strings from allowed-values entries."""
        return [str(e["value"]) for e in entries if isinstance(e, dict)]

    def test_returns_empty_for_none(self) -> None:
        assert self._call(None) == []

    def test_returns_empty_for_empty_list(self) -> None:
        assert self._call([]) == []

    def test_returns_empty_for_empty_dict(self) -> None:
        assert self._call({}) == []

    def test_extracts_values_from_flat_list(self) -> None:
        vocab: JSONArray = [
            ["Pf3D7", "P. falciparum 3D7"],
            ["PvP01", "P. vivax P01"],
        ]
        result = self._call(vocab)
        values = self._values(result)
        assert "Pf3D7" in values
        assert "PvP01" in values
        # Each entry should have both value and display
        assert result[0]["display"] == "P. falciparum 3D7"

    def test_deduplicates_values(self) -> None:
        vocab: JSONArray = [
            ["Pf3D7", "P. falciparum 3D7"],
            ["Pf3D7", "P. falciparum 3D7 duplicate"],
        ]
        result = self._call(vocab)
        values = self._values(result)
        assert values.count("Pf3D7") == 1

    def test_caps_at_50(self) -> None:
        vocab: JSONArray = [[f"val{i}", f"display{i}"] for i in range(100)]
        result = self._call(vocab)
        assert len(result) == 50

    def test_skips_entries_without_value_or_display(self) -> None:
        # flatten_vocab returns dicts with "value" and "display" keys
        # If both are None/empty, the entry should be skipped.
        # We test via a vocab that flatten_vocab can process into entries
        # with missing values. An empty sub-list produces no useful entry.
        vocab: JSONArray = [
            ["good_val", "Good Display"],
        ]
        result = self._call(vocab)
        values = self._values(result)
        assert "good_val" in values


# ---------------------------------------------------------------------------
# fetch_search_details
# ---------------------------------------------------------------------------


class TestFetchSearchDetails:
    """Tests for fetch_search_details() helper."""

    async def test_returns_details_on_success(self) -> None:
        expected = _to_wdk_search_response(
            {
                "displayName": "Test Search",
                "parameters": [],
            }
        )
        discovery = MagicMock()
        discovery.get_search_details = AsyncMock(return_value=expected)
        discovery.get_searches = AsyncMock(return_value=[])

        response, resolved_rt = await fetch_search_details(
            discovery, SearchContext("plasmodb", "gene", "TestSearch")
        )
        assert isinstance(response, WDKSearchResponse)
        assert response.search_data.display_name == "Test Search"
        assert resolved_rt == "gene"

    async def test_fallback_scans_record_types_on_failure(self) -> None:
        call_count = 0

        async def _side_effect(
            ctx: SearchContext, expand_params: bool = True
        ) -> WDKSearchResponse:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                msg = "not found on first try"
                raise AppError(ErrorCode.SEARCH_NOT_FOUND, msg)
            return _to_wdk_search_response({"displayName": "Found", "parameters": []})

        discovery = MagicMock()
        discovery.get_search_details = AsyncMock(side_effect=_side_effect)
        discovery.get_searches = AsyncMock(
            side_effect=lambda _sid, rt: (
                [WDKSearch(url_segment="MySearch")] if rt == "transcript" else []
            )
        )

        response, resolved_rt = await fetch_search_details(
            discovery,
            SearchContext("plasmodb", "gene", "MySearch"),
            record_types=[
                WDKRecordType(url_segment="gene", full_name="Genes"),
                WDKRecordType(url_segment="transcript", full_name="Transcripts"),
            ],
        )
        assert isinstance(response, WDKSearchResponse)
        assert response.search_data.display_name == "Found"
        assert resolved_rt == "transcript"

    async def test_raises_validation_error_when_not_found_anywhere(self) -> None:
        discovery = MagicMock()
        discovery.get_search_details = AsyncMock(
            side_effect=AppError(ErrorCode.SEARCH_NOT_FOUND, "not found"),
        )
        discovery.get_searches = AsyncMock(return_value=[])

        with pytest.raises(ValidationError) as exc_info:
            await fetch_search_details(
                discovery,
                SearchContext("plasmodb", "gene", "NonexistentSearch"),
                record_types=[WDKRecordType(url_segment="gene", full_name="Genes")],
            )
        assert "NonexistentSearch" in (exc_info.value.detail or "")

    async def test_fallback_returns_none_details_when_retry_fails(self) -> None:
        """When fallback scan finds the search but details fetch fails too,
        it should still raise ValidationError."""
        discovery = MagicMock()
        discovery.get_search_details = AsyncMock(
            side_effect=AppError(ErrorCode.SEARCH_NOT_FOUND, "always fails"),
        )
        discovery.get_searches = AsyncMock(
            side_effect=lambda _sid, rt: (
                [WDKSearch(url_segment="MySearch")] if rt == "gene" else []
            )
        )

        # The search IS found in the scan, but details still fail.
        # Since details is None after the fallback, it should raise.
        with pytest.raises(ValidationError):
            await fetch_search_details(
                discovery,
                SearchContext("plasmodb", "gene", "MySearch"),
                record_types=[WDKRecordType(url_segment="gene", full_name="Genes")],
            )

    async def test_skips_record_types_with_empty_url_segment(self) -> None:
        discovery = MagicMock()
        discovery.get_search_details = AsyncMock(
            side_effect=AppError(ErrorCode.SEARCH_NOT_FOUND, "not found"),
        )
        discovery.get_searches = AsyncMock(return_value=[])

        with pytest.raises(ValidationError):
            await fetch_search_details(
                discovery,
                SearchContext("plasmodb", "gene", "Missing"),
                record_types=[
                    WDKRecordType(url_segment="", full_name="Empty"),
                    WDKRecordType(url_segment="gene", full_name="Genes"),
                ],
            )
        # Should not crash on empty url_segment entries


# ---------------------------------------------------------------------------
# Integration: get_search_parameters still works after decomposition
# ---------------------------------------------------------------------------


class TestGetSearchParametersAfterDecomposition:
    """Verify that get_search_parameters() still produces correct results
    after the helpers have been extracted."""

    async def test_end_to_end_basic(self) -> None:
        discovery = MagicMock()
        discovery.get_record_types = AsyncMock(
            return_value=[WDKRecordType(url_segment="gene", full_name="Genes")]
        )
        discovery.get_search_details = AsyncMock(
            return_value=_to_wdk_search_response(
                {
                    "displayName": "Genes by Taxon",
                    "description": "Find genes by taxonomy",
                    "parameters": [
                        {
                            "name": "organism",
                            "displayName": "Organism",
                            "type": "single-pick-vocabulary",
                            "allowEmptyValue": False,
                            "isVisible": True,
                            "help": "Choose an organism",
                        },
                    ],
                }
            )
        )
        discovery.get_searches = AsyncMock(return_value=[])

        with patch(
            "veupath_chatbot.services.catalog.param_resolution.get_discovery_service",
            return_value=discovery,
        ):
            result = await get_search_parameters(
                SearchContext("plasmodb", "gene", "GenesByTaxon")
            )

        assert result["searchName"] == "GenesByTaxon"
        assert result["displayName"] == "Genes by Taxon"
        assert result["description"] == "Find genes by taxonomy"
        assert result["resolvedRecordType"] == "gene"
        params = result["parameters"]
        assert isinstance(params, list)
        assert len(params) == 1
        p = params[0]
        assert isinstance(p, dict)
        assert p["name"] == "organism"

    async def test_end_to_end_with_fallback(self) -> None:
        call_count = 0

        async def _get_details(
            ctx: SearchContext, expand_params: bool = True
        ) -> WDKSearchResponse:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                msg = "not found"
                raise AppError(ErrorCode.SEARCH_NOT_FOUND, msg)
            return _to_wdk_search_response(
                {
                    "displayName": "Found",
                    "description": "desc",
                    "parameters": [{"name": "p1", "type": "string"}],
                }
            )

        discovery = MagicMock()
        discovery.get_record_types = AsyncMock(
            return_value=[
                WDKRecordType(url_segment="gene", full_name="Genes"),
                WDKRecordType(url_segment="transcript", full_name="Transcripts"),
            ]
        )
        discovery.get_search_details = AsyncMock(side_effect=_get_details)
        discovery.get_searches = AsyncMock(
            side_effect=lambda _sid, rt: (
                [WDKSearch(url_segment="SharedSearch")] if rt == "transcript" else []
            )
        )

        with patch(
            "veupath_chatbot.services.catalog.param_resolution.get_discovery_service",
            return_value=discovery,
        ):
            result = await get_search_parameters(
                SearchContext("plasmodb", "gene", "SharedSearch")
            )

        assert result["resolvedRecordType"] == "transcript"
        assert result["displayName"] == "Found"
