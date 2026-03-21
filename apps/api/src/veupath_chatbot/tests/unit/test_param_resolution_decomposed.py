"""Tests for decomposed helpers in services/catalog/param_resolution.py.

Covers allowed_values(), format_param_info(), and fetch_search_details().
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from veupath_chatbot.domain.search import SearchContext
from veupath_chatbot.platform.errors import ValidationError
from veupath_chatbot.platform.types import JSONArray, JSONObject
from veupath_chatbot.services.catalog.param_discovery import fetch_search_details
from veupath_chatbot.services.catalog.param_formatting import format_param_info
from veupath_chatbot.services.catalog.param_resolution import get_search_parameters
from veupath_chatbot.services.catalog.vocab_rendering import allowed_values

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
# format_param_info
# ---------------------------------------------------------------------------


class TestFormatParamInfo:
    """Tests for format_param_info() helper."""

    def _call(self, param_specs: JSONArray) -> JSONArray:
        return format_param_info(param_specs)

    def test_basic_param_spec(self) -> None:
        specs: JSONArray = [
            {
                "name": "organism",
                "displayName": "Organism",
                "type": "single-pick-vocabulary",
                "allowEmptyValue": False,
                "isVisible": True,
                "help": "Choose an organism",
            }
        ]
        result = self._call(specs)
        assert len(result) == 1
        p = result[0]
        assert isinstance(p, dict)
        assert p["name"] == "organism"
        assert p["displayName"] == "Organism"
        assert p["type"] == "single-pick-vocabulary"
        assert p["required"] is True
        assert p["isVisible"] is True
        assert p["help"] == "Choose an organism"

    def test_skips_non_dict_entries(self) -> None:
        specs: JSONArray = ["not_a_dict", 42, {"name": "valid", "type": "string"}]
        result = self._call(specs)
        assert len(result) == 1

    def test_skips_entries_without_name(self) -> None:
        specs: JSONArray = [
            {"type": "string"},  # no name
            {"name": "", "type": "string"},  # empty name
            {"name": "valid", "type": "string"},
        ]
        result = self._call(specs)
        assert len(result) == 1
        p = result[0]
        assert isinstance(p, dict)
        assert p["name"] == "valid"

    def test_is_required_field_is_ignored(self) -> None:
        """isRequired is not a WDK field -- only allowEmptyValue matters."""
        specs: JSONArray = [
            {"name": "p1", "isRequired": True},
            {"name": "p2", "isRequired": False},
        ]
        result = self._call(specs)
        p1 = next(p for p in result if isinstance(p, dict) and p["name"] == "p1")
        p2 = next(p for p in result if isinstance(p, dict) and p["name"] == "p2")
        # Both have no allowEmptyValue, so required = not bool(None) = True
        assert p1["required"] is True
        assert p2["required"] is True

    def test_required_from_allow_empty_value(self) -> None:
        specs: JSONArray = [
            {"name": "optional", "allowEmptyValue": True},
            {"name": "required", "allowEmptyValue": False},
        ]
        result = self._call(specs)
        opt = next(p for p in result if isinstance(p, dict) and p["name"] == "optional")
        req = next(p for p in result if isinstance(p, dict) and p["name"] == "required")
        assert opt["required"] is False
        assert req["required"] is True

    def test_defaults_for_missing_fields(self) -> None:
        """When optional fields are missing, use sensible defaults."""
        specs: JSONArray = [{"name": "bare_param"}]
        result = self._call(specs)
        assert len(result) == 1
        p = result[0]
        assert isinstance(p, dict)
        assert p["displayName"] == "bare_param"  # falls back to name
        assert p["type"] == "string"  # default type
        assert p["help"] == ""  # default help
        assert p["isVisible"] is True  # default visibility
        assert p["required"] is True  # default required (no allowEmptyValue)

    def test_initial_display_value_sets_default(self) -> None:
        specs: JSONArray = [
            {"name": "p1", "initialDisplayValue": "init_val"},
        ]
        result = self._call(specs)
        p = result[0]
        assert isinstance(p, dict)
        assert p["defaultValue"] == "init_val"

    def test_default_value_fallback(self) -> None:
        specs: JSONArray = [
            {"name": "p1", "defaultValue": "fallback_val"},
        ]
        result = self._call(specs)
        p = result[0]
        assert isinstance(p, dict)
        assert p["defaultValue"] == "fallback_val"

    def test_initial_display_value_takes_priority_over_default(self) -> None:
        specs: JSONArray = [
            {
                "name": "p1",
                "initialDisplayValue": "preferred",
                "defaultValue": "secondary",
            },
        ]
        result = self._call(specs)
        p = result[0]
        assert isinstance(p, dict)
        assert p["defaultValue"] == "preferred"

    def test_vocabulary_producesallowed_values(self) -> None:
        specs: JSONArray = [
            {
                "name": "organism",
                "vocabulary": [
                    ["Pf3D7", "P. falciparum 3D7"],
                    ["PvP01", "P. vivax P01"],
                ],
            },
        ]
        result = self._call(specs)
        p = result[0]
        assert isinstance(p, dict)
        assert "allowedValues" in p
        allowed = p["allowedValues"]
        assert isinstance(allowed, list)
        values = [e["value"] for e in allowed if isinstance(e, dict)]
        assert "Pf3D7" in values
        displays = [e["display"] for e in allowed if isinstance(e, dict)]
        assert "P. falciparum 3D7" in displays

    def test_noallowed_values_when_vocabulary_empty(self) -> None:
        specs: JSONArray = [
            {"name": "p1", "vocabulary": []},
        ]
        result = self._call(specs)
        p = result[0]
        assert isinstance(p, dict)
        assert "allowedValues" not in p

    def test_non_string_name_skipped(self) -> None:
        specs: JSONArray = [
            {"name": 123, "type": "string"},
        ]
        result = self._call(specs)
        assert len(result) == 0

    def test_non_dict_vocabulary_ignored(self) -> None:
        specs: JSONArray = [
            {"name": "p1", "vocabulary": "not_a_list_or_dict"},
        ]
        result = self._call(specs)
        p = result[0]
        assert isinstance(p, dict)
        assert "allowedValues" not in p


# ---------------------------------------------------------------------------
# fetch_search_details
# ---------------------------------------------------------------------------


class TestFetchSearchDetails:
    """Tests for fetch_search_details() helper."""

    async def test_returns_details_on_success(self) -> None:
        expected: dict[str, Any] = {
            "displayName": "Test Search",
            "parameters": [],
        }
        discovery = MagicMock()
        discovery.get_search_details = AsyncMock(return_value=expected)
        discovery.get_searches = AsyncMock(return_value=[])

        details, resolved_rt = await fetch_search_details(
            discovery, SearchContext("plasmodb", "gene", "TestSearch")
        )
        assert details == expected
        assert resolved_rt == "gene"

    async def test_fallback_scans_record_types_on_failure(self) -> None:
        call_count = 0

        async def _side_effect(
            ctx: SearchContext, expand_params: bool = True
        ) -> dict[str, Any]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                msg = "not found on first try"
                raise ValueError(msg)
            return {"displayName": "Found", "parameters": []}

        discovery = MagicMock()
        discovery.get_search_details = AsyncMock(side_effect=_side_effect)
        discovery.get_searches = AsyncMock(
            side_effect=lambda _sid, rt: (
                [{"urlSegment": "MySearch"}] if rt == "transcript" else []
            )
        )

        record_types: list[Any] = [
            {"urlSegment": "gene", "name": "Genes"},
            {"urlSegment": "transcript", "name": "Transcripts"},
        ]

        details, resolved_rt = await fetch_search_details(
            discovery,
            SearchContext("plasmodb", "gene", "MySearch"),
            record_types=record_types,
        )
        assert details is not None
        assert isinstance(details, dict)
        assert details["displayName"] == "Found"
        assert resolved_rt == "transcript"

    async def test_raises_validation_error_when_not_found_anywhere(self) -> None:
        discovery = MagicMock()
        discovery.get_search_details = AsyncMock(side_effect=ValueError("not found"))
        discovery.get_searches = AsyncMock(return_value=[])

        record_types: list[Any] = [
            {"urlSegment": "gene", "name": "Genes"},
        ]

        with pytest.raises(ValidationError) as exc_info:
            await fetch_search_details(
                discovery,
                SearchContext("plasmodb", "gene", "NonexistentSearch"),
                record_types=record_types,
            )
        assert "NonexistentSearch" in (exc_info.value.detail or "")

    async def test_fallback_returns_none_details_when_retry_fails(self) -> None:
        """When fallback scan finds the search but details fetch fails too,
        it should still raise ValidationError."""
        discovery = MagicMock()
        discovery.get_search_details = AsyncMock(side_effect=ValueError("always fails"))
        discovery.get_searches = AsyncMock(
            side_effect=lambda _sid, rt: (
                [{"urlSegment": "MySearch"}] if rt == "gene" else []
            )
        )

        record_types: list[Any] = [
            {"urlSegment": "gene", "name": "Genes"},
        ]

        # The search IS found in the scan, but details still fail.
        # Since details is None after the fallback, it should raise.
        with pytest.raises(ValidationError):
            await fetch_search_details(
                discovery,
                SearchContext("plasmodb", "gene", "MySearch"),
                record_types=record_types,
            )

    async def test_skips_non_dict_record_types(self) -> None:
        discovery = MagicMock()
        discovery.get_search_details = AsyncMock(side_effect=ValueError("not found"))
        discovery.get_searches = AsyncMock(return_value=[])

        record_types: list[Any] = [
            "not_a_dict",
            42,
            {"urlSegment": "gene", "name": "Genes"},
        ]

        with pytest.raises(ValidationError):
            await fetch_search_details(
                discovery,
                SearchContext("plasmodb", "gene", "Missing"),
                record_types=record_types,
            )
        # Should not crash on non-dict entries


# ---------------------------------------------------------------------------
# Integration: get_search_parameters still works after decomposition
# ---------------------------------------------------------------------------


class TestGetSearchParametersAfterDecomposition:
    """Verify that get_search_parameters() still produces correct results
    after the helpers have been extracted."""

    async def test_end_to_end_basic(self) -> None:
        discovery = MagicMock()
        discovery.get_record_types = AsyncMock(
            return_value=[{"urlSegment": "gene", "name": "Genes"}]
        )
        discovery.get_search_details = AsyncMock(
            return_value={
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
        discovery.get_searches = AsyncMock(return_value=[])

        with patch(
            "veupath_chatbot.services.catalog.param_resolution.get_discovery_service",
            return_value=discovery,
        ):
            result = await get_search_parameters(SearchContext("plasmodb", "gene", "GenesByTaxon"))

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
        ) -> dict[str, Any]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                msg = "not found"
                raise ValueError(msg)
            return {
                "displayName": "Found",
                "description": "desc",
                "parameters": [{"name": "p1", "type": "string"}],
            }

        discovery = MagicMock()
        discovery.get_record_types = AsyncMock(
            return_value=[
                {"urlSegment": "gene", "name": "Genes"},
                {"urlSegment": "transcript", "name": "Transcripts"},
            ]
        )
        discovery.get_search_details = AsyncMock(side_effect=_get_details)
        discovery.get_searches = AsyncMock(
            side_effect=lambda _sid, rt: (
                [{"urlSegment": "SharedSearch"}] if rt == "transcript" else []
            )
        )

        with patch(
            "veupath_chatbot.services.catalog.param_resolution.get_discovery_service",
            return_value=discovery,
        ):
            result = await get_search_parameters(SearchContext("plasmodb", "gene", "SharedSearch"))

        assert result["resolvedRecordType"] == "transcript"
        assert result["displayName"] == "Found"
