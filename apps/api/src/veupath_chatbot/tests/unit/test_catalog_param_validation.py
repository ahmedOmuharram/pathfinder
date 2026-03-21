"""Unit tests for services/catalog/param_validation.py.

Covers validate_search_params() with mocked expand_search_details_with_params().
"""

from typing import Any
from unittest.mock import AsyncMock, patch

from veupath_chatbot.domain.search import SearchContext
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    WDKSearch,
    WDKSearchResponse,
    WDKValidation,
)
from veupath_chatbot.platform.errors import AppError, ErrorCode
from veupath_chatbot.services.catalog.param_validation import validate_search_params

# ---------------------------------------------------------------------------
# Helpers
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


def _to_wdk_search_response(details: dict[str, Any] | None) -> WDKSearchResponse:
    """Convert a raw dict to WDKSearchResponse."""
    if not details:
        return WDKSearchResponse(
            search_data=WDKSearch(url_segment="unknown"),
            validation=WDKValidation(),
        )
    normalized = _normalize_search_dict(details)
    search = WDKSearch.model_validate(normalized)
    return WDKSearchResponse(search_data=search, validation=WDKValidation())


def _patch_expand(
    return_value: dict[str, Any] | None = None,
    side_effect: Exception | None = None,
) -> Any:
    """Patch expand_search_details_with_params."""
    if side_effect:
        # Convert ValueError to AppError for the service layer
        if isinstance(side_effect, ValueError):
            side_effect = AppError(ErrorCode.INTERNAL_ERROR, str(side_effect))
        return patch(
            "veupath_chatbot.services.catalog.param_validation.expand_search_details_with_params",
            new_callable=AsyncMock,
            side_effect=side_effect,
        )
    return patch(
        "veupath_chatbot.services.catalog.param_validation.expand_search_details_with_params",
        new_callable=AsyncMock,
        return_value=_to_wdk_search_response(return_value),
    )


def _as_dict(val: object) -> dict[str, Any]:
    """Narrow a JSONValue to dict for test assertions."""
    assert isinstance(val, dict)
    return val


def _get_validation(result: dict[str, Any]) -> dict[str, Any]:
    """Extract the validation sub-dict from the result."""
    return _as_dict(result["validation"])


def _get_errors(result: dict[str, Any]) -> dict[str, Any]:
    """Extract the errors sub-dict from the validation result."""
    return _as_dict(_get_validation(result)["errors"])


# ---------------------------------------------------------------------------
# validate_search_params -- happy path
# ---------------------------------------------------------------------------


class TestValidateSearchParamsValid:
    """Test validation when parameters are valid."""

    async def test_valid_params_returns_is_valid_true(self) -> None:
        details: dict[str, Any] = {
            "parameters": [
                {
                    "name": "organism",
                    "type": "string",
                    "allowEmptyValue": True,
                },
            ]
        }
        with _patch_expand(return_value=details):
            result = await validate_search_params(
                SearchContext("plasmodb", "gene", "GenesByTaxon"),
                context_values={"organism": "Pf3D7"},
            )

        validation = _get_validation(result)
        errors = _get_errors(result)
        assert validation["isValid"] is True
        assert errors["general"] == []
        assert errors["byKey"] == {}

    async def test_empty_context_with_no_required_params(self) -> None:
        details: dict[str, Any] = {
            "parameters": [
                {
                    "name": "optional_param",
                    "type": "string",
                    "allowEmptyValue": True,
                },
            ]
        }
        with _patch_expand(return_value=details):
            result = await validate_search_params(
                SearchContext("plasmodb", "gene", "S"),
                context_values={},
            )

        assert _get_validation(result)["isValid"] is True

    async def test_none_context_treated_as_empty(self) -> None:
        details: dict[str, Any] = {"parameters": []}
        with _patch_expand(return_value=details):
            result = await validate_search_params(
                SearchContext("plasmodb", "gene", "S"),
                context_values=None,
            )

        assert _get_validation(result)["isValid"] is True

    async def test_normalized_values_in_response(self) -> None:
        """The normalizedContextValues should be populated on success."""
        details: dict[str, Any] = {
            "parameters": [
                {
                    "name": "organism",
                    "type": "string",
                    "allowEmptyValue": True,
                },
            ]
        }
        with _patch_expand(return_value=details):
            result = await validate_search_params(
                SearchContext("plasmodb", "gene", "S"),
                context_values={"organism": "Pf3D7"},
            )

        validation = _get_validation(result)
        assert "normalizedContextValues" in validation


# ---------------------------------------------------------------------------
# validate_search_params -- error cases
# ---------------------------------------------------------------------------


class TestValidateSearchParamsErrors:
    """Test validation error handling."""

    async def test_expand_failure_returns_is_valid_false(self) -> None:
        with _patch_expand(side_effect=ValueError("Network error")):
            result = await validate_search_params(
                SearchContext("plasmodb", "gene", "S"),
                context_values={"organism": "Pf3D7"},
            )

        validation = _get_validation(result)
        errors = _get_errors(result)
        general = errors["general"]
        assert isinstance(general, list)
        assert validation["isValid"] is False
        assert any("Network error" in str(msg) for msg in general)

    async def test_missing_required_params_returns_is_valid_false(self) -> None:
        details: dict[str, Any] = {
            "parameters": [
                {
                    "name": "organism",
                    "type": "string",
                    "allowEmptyValue": False,
                },
            ]
        }
        with _patch_expand(return_value=details):
            result = await validate_search_params(
                SearchContext("plasmodb", "gene", "S"),
                context_values={},
            )

        validation = _get_validation(result)
        errors = _get_errors(result)
        by_key = _as_dict(errors["byKey"])
        assert validation["isValid"] is False
        assert "organism" in by_key
        assert by_key["organism"] == ["Required"]

    async def test_multiple_missing_required_params(self) -> None:
        details: dict[str, Any] = {
            "parameters": [
                {
                    "name": "organism",
                    "type": "string",
                    "allowEmptyValue": False,
                },
                {
                    "name": "taxon",
                    "type": "string",
                    "allowEmptyValue": False,
                },
            ]
        }
        with _patch_expand(return_value=details):
            result = await validate_search_params(
                SearchContext("plasmodb", "gene", "S"),
                context_values={},
            )

        validation = _get_validation(result)
        by_key = _as_dict(_get_errors(result)["byKey"])
        assert validation["isValid"] is False
        assert "organism" in by_key
        assert "taxon" in by_key

    async def test_empty_value_for_required_param(self) -> None:
        details: dict[str, Any] = {
            "parameters": [
                {
                    "name": "organism",
                    "type": "string",
                    "allowEmptyValue": False,
                },
            ]
        }
        with _patch_expand(return_value=details):
            result = await validate_search_params(
                SearchContext("plasmodb", "gene", "S"),
                context_values={"organism": ""},
            )

        assert _get_validation(result)["isValid"] is False


# ---------------------------------------------------------------------------
# validate_search_params -- response structure
# ---------------------------------------------------------------------------


class TestValidateSearchParamsStructure:
    """Test the response structure invariants."""

    async def test_always_has_validation_key(self) -> None:
        with _patch_expand(return_value={"parameters": []}):
            result = await validate_search_params(
                SearchContext("plasmodb", "gene", "S"),
                context_values={},
            )

        assert "validation" in result

    async def test_validation_has_required_keys(self) -> None:
        with _patch_expand(return_value={"parameters": []}):
            result = await validate_search_params(
                SearchContext("plasmodb", "gene", "S"),
                context_values={},
            )

        validation = _get_validation(result)
        assert "isValid" in validation
        assert "normalizedContextValues" in validation
        assert "errors" in validation

    async def test_errors_has_general_and_by_key(self) -> None:
        with _patch_expand(return_value={"parameters": []}):
            result = await validate_search_params(
                SearchContext("plasmodb", "gene", "S"),
                context_values={},
            )

        errors = _get_errors(result)
        assert "general" in errors
        assert "byKey" in errors

    async def test_error_response_structure_on_expand_failure(self) -> None:
        with _patch_expand(side_effect=ValueError("fail")):
            result = await validate_search_params(
                SearchContext("plasmodb", "gene", "S"),
                context_values={},
            )

        validation = _get_validation(result)
        errors = _get_errors(result)
        assert validation["isValid"] is False
        assert validation["normalizedContextValues"] == {}
        assert isinstance(errors["general"], list)
        assert isinstance(errors["byKey"], dict)

    async def test_missing_required_error_structure(self) -> None:
        details: dict[str, Any] = {
            "parameters": [
                {
                    "name": "organism",
                    "type": "string",
                    "allowEmptyValue": False,
                },
            ]
        }
        with _patch_expand(return_value=details):
            result = await validate_search_params(
                SearchContext("plasmodb", "gene", "S"),
                context_values={},
            )

        validation = _get_validation(result)
        assert validation["isValid"] is False
        # normalizedContextValues should still be present (may be empty or partial)
        assert "normalizedContextValues" in validation
        # general error should mention missing params
        general = _get_errors(result)["general"]
        assert isinstance(general, list)
        assert any("Missing required" in str(g) for g in general)


# ---------------------------------------------------------------------------
# validate_search_params -- canonicalization error handling
# ---------------------------------------------------------------------------


class TestValidateSearchParamsCanonicalizationErrors:
    """Test handling of ValidationError from ParameterCanonicalizer."""

    async def test_unknown_params_filtered_silently(self) -> None:
        """Unknown params are filtered by _filter_context_values before canonicalization.

        This is intentional -- the filtering prevents unknown-param errors.
        """
        details: dict[str, Any] = {
            "parameters": [
                {
                    "name": "known_param",
                    "type": "string",
                    "allowEmptyValue": True,
                },
            ]
        }
        with _patch_expand(return_value=details):
            result = await validate_search_params(
                SearchContext("plasmodb", "gene", "S"),
                context_values={"unknown_param": "value"},
            )

        # Unknown params are silently dropped, so validation succeeds
        assert _get_validation(result)["isValid"] is True

    async def test_canonicalization_error_for_scalar_param_given_list(self) -> None:
        """A scalar param given a list value should cause a canonicalization error."""
        details: dict[str, Any] = {
            "parameters": [
                {
                    "name": "scalar_param",
                    "type": "string",
                    "allowEmptyValue": True,
                },
            ]
        }
        with _patch_expand(return_value=details):
            result = await validate_search_params(
                SearchContext("plasmodb", "gene", "S"),
                context_values={"scalar_param": ["a", "b"]},
            )

        validation = _get_validation(result)
        errors = _get_errors(result)
        general = errors["general"]
        assert isinstance(general, list)
        assert validation["isValid"] is False
        assert len(general) > 0

    async def test_multi_pick_required_empty_value(self) -> None:
        """A required multi-pick param with empty value should fail."""
        details: dict[str, Any] = {
            "parameters": [
                {
                    "name": "organisms",
                    "type": "multi-pick-vocabulary",
                    "allowEmptyValue": False,
                },
            ]
        }
        with _patch_expand(return_value=details):
            result = await validate_search_params(
                SearchContext("plasmodb", "gene", "S"),
                context_values={"organisms": "[]"},
            )

        assert _get_validation(result)["isValid"] is False
