"""Tests for services/catalog/parameters.py re-exports and
additional edge cases in param_resolution.py and param_validation.py
not covered by their dedicated test files.

Focus areas:
  - parameters.py __all__ re-exports work
  - _extract_param_names with nested searchData that has a dict parameters
  - _filter_context_values behavior with both empty allowed set and non-empty
  - validate_search_params with nested canonical/error handling
  - get_search_parameters with non-standard parameter specs
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from veupath_chatbot.domain.parameters.specs import unwrap_search_data
from veupath_chatbot.domain.search import SearchContext
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    WDKRecordType,
    WDKSearch,
    WDKSearchResponse,
    WDKValidation,
)
from veupath_chatbot.services.catalog.param_resolution import (
    _filter_context_values,
)
from veupath_chatbot.services.catalog.parameters import (
    expand_search_details_with_params,
    get_search_parameters,
    get_search_parameters_tool,
    validate_search_params,
)

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
# parameters.py re-exports
# ---------------------------------------------------------------------------


class TestParametersReExports:
    """Verify that parameters.py correctly re-exports the public API."""

    def test_get_search_parameters_is_callable(self) -> None:
        assert callable(get_search_parameters)

    def test_get_search_parameters_tool_is_callable(self) -> None:
        assert callable(get_search_parameters_tool)

    def test_expand_search_details_with_params_is_callable(self) -> None:
        assert callable(expand_search_details_with_params)

    def test_validate_search_params_is_callable(self) -> None:
        assert callable(validate_search_params)


# ---------------------------------------------------------------------------
# _filter_context_values additional edge cases
# ---------------------------------------------------------------------------


class TestFilterContextValuesEdgeCases:
    """Additional edge cases for _filter_context_values."""

    def test_preserves_all_value_types(self) -> None:
        """Should preserve any JSON value type (list, dict, bool, int, etc)."""
        raw: dict[str, Any] = {
            "str_param": "value",
            "list_param": ["a", "b"],
            "int_param": 42,
            "bool_param": True,
            "dict_param": {"nested": "value"},
        }
        allowed = {"str_param", "list_param", "int_param", "bool_param", "dict_param"}
        result = _filter_context_values(raw, allowed)
        assert result == raw

    def test_empty_raw_empty_allowed(self) -> None:
        result = _filter_context_values({}, set())
        assert result == {}

    def test_case_sensitive_keys(self) -> None:
        """Keys should be case-sensitive."""
        raw: dict[str, Any] = {"Organism": "val"}
        allowed = {"organism"}
        result = _filter_context_values(raw, allowed)
        assert result == {}


# ---------------------------------------------------------------------------
# unwrap_search_data edge cases (param_resolution version)
# ---------------------------------------------------------------------------


class TestUnwrapSearchDataResolution:
    """Edge cases for unwrap_search_data in param_resolution.py."""

    def test_empty_dict_returns_itself(self) -> None:
        result = unwrap_search_data({})
        assert result == {}

    def test_search_data_empty_dict_returns_inner(self) -> None:
        """An empty searchData dict should still unwrap."""
        result = unwrap_search_data({"searchData": {}})
        assert result == {}

    def test_search_data_with_nested_search_data(self) -> None:
        """Only one level of unwrapping."""
        inner = {"searchData": {"displayName": "Deep"}}
        result = unwrap_search_data({"searchData": inner})
        assert result is inner
        # The inner searchData is not further unwrapped
        assert "searchData" in result


# ---------------------------------------------------------------------------
# get_search_parameters with unknown parameter types
# ---------------------------------------------------------------------------


class TestGetSearchParametersUnknownTypes:
    """Test get_search_parameters with unusual parameter types."""

    async def test_unknown_param_type_defaults_to_string(self) -> None:
        discovery = MagicMock()
        discovery.get_record_types = AsyncMock(return_value=[WDKRecordType(url_segment="gene")])
        discovery.get_search_details = AsyncMock(
            return_value=_to_wdk_search_response({
                "parameters": [
                    {
                        "name": "custom_param",
                        "displayName": "Custom",
                    },
                ]
            })
        )

        with patch(
            "veupath_chatbot.services.catalog.param_resolution.get_discovery_service",
            return_value=discovery,
        ):
            result = await get_search_parameters(SearchContext("plasmodb", "gene", "S"))

        params = result["parameters"]
        assert isinstance(params, list)
        assert len(params) == 1
        p = params[0]
        assert isinstance(p, dict)
        assert p["type"] == "string"  # default

    async def test_parameter_visibility_default_true(self) -> None:
        discovery = MagicMock()
        discovery.get_record_types = AsyncMock(return_value=[WDKRecordType(url_segment="gene")])
        discovery.get_search_details = AsyncMock(
            return_value=_to_wdk_search_response({
                "parameters": [
                    {"name": "param1", "type": "string"},
                ]
            })
        )

        with patch(
            "veupath_chatbot.services.catalog.param_resolution.get_discovery_service",
            return_value=discovery,
        ):
            result = await get_search_parameters(SearchContext("plasmodb", "gene", "S"))

        params = result["parameters"]
        assert isinstance(params, list)
        p = params[0]
        assert isinstance(p, dict)
        assert p["isVisible"] is True

    async def test_parameter_visibility_explicit_false(self) -> None:
        """Hidden params (isVisible=False) are included with their flag for the AI."""
        discovery = MagicMock()
        discovery.get_record_types = AsyncMock(return_value=[WDKRecordType(url_segment="gene")])
        discovery.get_search_details = AsyncMock(
            return_value=_to_wdk_search_response({
                "parameters": [
                    {"name": "hidden", "type": "string", "isVisible": False},
                ]
            })
        )

        with patch(
            "veupath_chatbot.services.catalog.param_resolution.get_discovery_service",
            return_value=discovery,
        ):
            result = await get_search_parameters(SearchContext("plasmodb", "gene", "S"))

        params = result["parameters"]
        assert isinstance(params, list)
        assert len(params) == 1
        assert params[0]["isVisible"] is False

    async def test_no_default_value_when_both_absent(self) -> None:
        """When neither initialDisplayValue nor defaultValue are present."""
        discovery = MagicMock()
        discovery.get_record_types = AsyncMock(return_value=[WDKRecordType(url_segment="gene")])
        discovery.get_search_details = AsyncMock(
            return_value=_to_wdk_search_response({
                "parameters": [
                    {"name": "param1", "type": "string"},
                ]
            })
        )

        with patch(
            "veupath_chatbot.services.catalog.param_resolution.get_discovery_service",
            return_value=discovery,
        ):
            result = await get_search_parameters(SearchContext("plasmodb", "gene", "S"))

        params = result["parameters"]
        assert isinstance(params, list)
        p = params[0]
        assert isinstance(p, dict)
        assert "defaultValue" not in p

    async def test_required_defaults_to_true_without_explicit_flags(self) -> None:
        """When allowEmptyValue is absent, required = not bool(None) = True."""
        discovery = MagicMock()
        discovery.get_record_types = AsyncMock(return_value=[WDKRecordType(url_segment="gene")])
        discovery.get_search_details = AsyncMock(
            return_value=_to_wdk_search_response({
                "parameters": [
                    {"name": "param1", "type": "string"},
                ]
            })
        )

        with patch(
            "veupath_chatbot.services.catalog.param_resolution.get_discovery_service",
            return_value=discovery,
        ):
            result = await get_search_parameters(SearchContext("plasmodb", "gene", "S"))

        params = result["parameters"]
        assert isinstance(params, list)
        p = params[0]
        assert isinstance(p, dict)
        # allowEmptyValue is None => not bool(None) => True (required)
        assert p["required"] is True

    async def test_empty_vocabulary_produces_no_allowed_values(self) -> None:
        discovery = MagicMock()
        discovery.get_record_types = AsyncMock(return_value=[WDKRecordType(url_segment="gene")])
        discovery.get_search_details = AsyncMock(
            return_value=_to_wdk_search_response({
                "parameters": [
                    {
                        "name": "param1",
                        "type": "single-pick-vocabulary",
                        "vocabulary": [],
                    },
                ]
            })
        )

        with patch(
            "veupath_chatbot.services.catalog.param_resolution.get_discovery_service",
            return_value=discovery,
        ):
            result = await get_search_parameters(SearchContext("plasmodb", "gene", "S"))

        params = result["parameters"]
        assert isinstance(params, list)
        p = params[0]
        assert isinstance(p, dict)
        # Empty vocabulary means no allowed values entry
        assert "allowedValues" not in p

    async def test_display_name_from_details_not_summary(self) -> None:
        """displayName in the top-level result should come from details when available."""
        discovery = MagicMock()
        discovery.get_record_types = AsyncMock(return_value=[WDKRecordType(url_segment="gene")])
        discovery.get_search_details = AsyncMock(
            return_value=_to_wdk_search_response({
                "displayName": "Details Display",
                "description": "From details",
                "parameters": [],
            })
        )

        with patch(
            "veupath_chatbot.services.catalog.param_resolution.get_discovery_service",
            return_value=discovery,
        ):
            result = await get_search_parameters(SearchContext("plasmodb", "gene", "S"))

        assert result["displayName"] == "Details Display"
        assert result["description"] == "From details"
