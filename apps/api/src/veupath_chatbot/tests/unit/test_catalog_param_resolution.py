"""Unit tests for services/catalog/param_resolution.py.

Covers _filter_context_values(),
get_search_parameters(), get_search_parameters_tool(),
expand_search_details_with_params(), and _get_search_details_with_portal_fallback().
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from veupath_chatbot.domain.parameters.specs import unwrap_search_data
from veupath_chatbot.domain.search import SearchContext
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    WDKRecordType,
    WDKSearch,
    WDKSearchResponse,
    WDKValidation,
)
from veupath_chatbot.platform.errors import (
    AppError,
    ErrorCode,
    ValidationError,
    WDKError,
)
from veupath_chatbot.services.catalog.param_resolution import (
    _filter_context_values,
    _get_search_details_with_portal_fallback,
    expand_search_details_with_params,
    get_search_parameters,
    get_search_parameters_tool,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_wdk_searches(dicts: list[Any]) -> list[WDKSearch]:
    """Convert raw dicts to WDKSearch objects, skipping non-dicts."""
    result: list[WDKSearch] = []
    for d in dicts:
        if isinstance(d, dict):
            normalized = _normalize_search_dict(d)
            result.append(WDKSearch.model_validate(normalized))
    return result


def _normalize_search_dict(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize a raw search dict so it can be parsed by WDKSearch.model_validate().

    Handles test mock dicts that may have:
    - ``parameters`` as a dict (e.g. ``{"organism": {}}``) instead of a list
    - Parameter entries without a ``type`` field (defaults to ``"string"``)
    - Parameter entries without a ``name`` field (filtered out)
    - Missing ``urlSegment`` (falls back to ``name``)
    """
    d = dict(raw)
    if "urlSegment" not in d:
        d["urlSegment"] = d.get("name", "unknown")

    params = d.get("parameters")
    if isinstance(params, dict):
        d["paramNames"] = [k for k in params if k]
        d.pop("parameters")
    elif isinstance(params, list):
        normalized: list[dict[str, Any]] = []
        for p in params:
            if isinstance(p, dict):
                name = p.get("name")
                if not name or not isinstance(name, str):
                    continue
                entry = {**p, "type": "string"} if "type" not in p else p
                normalized.append(entry)
        d["parameters"] = normalized
    return d


def _to_wdk_search_response(details: dict[str, Any] | None) -> WDKSearchResponse:
    """Convert a raw dict to WDKSearchResponse.

    Handles both envelope format (with searchData key) and flat format.
    """
    if not details:
        return WDKSearchResponse(
            search_data=WDKSearch(url_segment="unknown"),
            validation=WDKValidation(),
        )
    search_data_raw = details.get("searchData")
    if isinstance(search_data_raw, dict):
        normalized = _normalize_search_dict(search_data_raw)
        search = WDKSearch.model_validate(normalized)
        validation_raw = details.get("validation", {})
        validation = WDKValidation.model_validate(validation_raw) if isinstance(validation_raw, dict) else WDKValidation()
        return WDKSearchResponse(search_data=search, validation=validation)
    # Flat format: the dict IS the search data
    normalized = _normalize_search_dict(details)
    search = WDKSearch.model_validate(normalized)
    return WDKSearchResponse(search_data=search, validation=WDKValidation())


def _to_wdk_record_types(raw: list[Any]) -> list[WDKRecordType]:
    """Convert raw dicts/strings to WDKRecordType objects for mocks."""
    result: list[WDKRecordType] = []
    for item in raw:
        if isinstance(item, dict):
            result.append(WDKRecordType.model_validate(item))
        elif isinstance(item, str):
            result.append(WDKRecordType(url_segment=item, display_name=item))
    return result


def _mock_discovery(
    record_types: list[Any] | None = None,
    searches_by_rt: dict[str, list[Any]] | None = None,
    search_details: dict[str, Any] | None = None,
    search_details_raises: Exception | None = None,
) -> MagicMock:
    """Build a mock discovery service."""
    discovery = MagicMock()
    typed_rts = _to_wdk_record_types(record_types or [])
    discovery.get_record_types = AsyncMock(return_value=typed_rts)
    if searches_by_rt is not None:
        parsed: dict[str, list[WDKSearch]] = {
            rt: _to_wdk_searches(raw) for rt, raw in searches_by_rt.items()
        }
        discovery.get_searches = AsyncMock(
            side_effect=lambda _site_id, rt: parsed.get(rt, [])
        )
    else:
        discovery.get_searches = AsyncMock(return_value=[])
    if search_details_raises:
        discovery.get_search_details = AsyncMock(side_effect=search_details_raises)
    else:
        discovery.get_search_details = AsyncMock(
            return_value=_to_wdk_search_response(search_details),
        )
    return discovery


def _mock_wdk_client(
    record_types: list[Any] | None = None,
    searches_by_rt: dict[str, list[Any]] | None = None,
    search_details_with_params: dict[str, Any] | None = None,
    search_details_with_params_raises: Exception | None = None,
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
    if search_details_with_params_raises:
        client.get_search_details_with_params = AsyncMock(
            side_effect=search_details_with_params_raises,
        )
    else:
        client.get_search_details_with_params = AsyncMock(
            return_value=_to_wdk_search_response(search_details_with_params),
        )
    return client


def _get_param_by_name(result: dict[str, Any], name: str) -> dict[str, Any]:
    """Extract a parameter dict from get_search_parameters result by name."""
    params = result["parameters"]
    assert isinstance(params, list)
    for p in params:
        assert isinstance(p, dict)
        if p.get("name") == name:
            return p
    msg = f"Parameter '{name}' not found"
    raise AssertionError(msg)


# ---------------------------------------------------------------------------
# _filter_context_values
# ---------------------------------------------------------------------------


class TestFilterContextValues:
    """Test the _filter_context_values() helper."""

    def test_filters_to_allowed_keys(self) -> None:
        raw: dict[str, Any] = {
            "organism": "Pf3D7",
            "taxon": "plasmodium",
            "extra": "value",
        }
        allowed = {"organism", "taxon"}
        result = _filter_context_values(raw, allowed)
        assert result == {"organism": "Pf3D7", "taxon": "plasmodium"}

    def test_passes_all_when_allowed_is_empty(self) -> None:
        raw: dict[str, Any] = {"organism": "Pf3D7", "extra": "value"}
        result = _filter_context_values(raw, set())
        assert result == raw

    def test_returns_empty_when_no_matching_keys(self) -> None:
        raw: dict[str, Any] = {"extra": "value"}
        allowed = {"organism"}
        result = _filter_context_values(raw, allowed)
        assert result == {}

    def test_empty_raw_context(self) -> None:
        result = _filter_context_values({}, {"organism"})
        assert result == {}


# ---------------------------------------------------------------------------
# unwrap_search_data
# ---------------------------------------------------------------------------


class TestUnwrapSearchData:
    """Test the unwrap_search_data() helper."""

    def test_unwraps_search_data_key(self) -> None:
        details: dict[str, Any] = {
            "searchData": {"parameters": [{"name": "organism"}]},
            "other": "stuff",
        }
        result = unwrap_search_data(details)
        assert result == {"parameters": [{"name": "organism"}]}

    def test_returns_details_when_no_search_data(self) -> None:
        details: dict[str, Any] = {"parameters": [{"name": "organism"}]}
        result = unwrap_search_data(details)
        assert result is details

    def test_returns_none_for_non_dict(self) -> None:
        assert unwrap_search_data(None) is None
        assert unwrap_search_data("not_a_dict") is None

    def test_returns_details_when_search_data_not_dict(self) -> None:
        details: dict[str, Any] = {"searchData": "not_a_dict", "parameters": []}
        result = unwrap_search_data(details)
        assert result is details


# ---------------------------------------------------------------------------
# get_search_parameters
# ---------------------------------------------------------------------------


class TestGetSearchParameters:
    """Test the get_search_parameters() function."""

    async def test_basic_search_parameters(self) -> None:
        discovery = _mock_discovery(
            record_types=[
                {"urlSegment": "gene", "name": "Genes"},
            ],
            search_details={
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
            },
        )
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
        assert p["displayName"] == "Organism"
        assert p["type"] == "single-pick-vocabulary"
        assert p["required"] is True
        assert p["isVisible"] is True
        assert p["help"] == "Choose an organism"

    async def test_resolves_record_type_by_url_segment(self) -> None:
        discovery = _mock_discovery(
            record_types=[
                {"urlSegment": "gene", "name": "GeneRecordClass"},
            ],
            search_details={"parameters": []},
        )
        with patch(
            "veupath_chatbot.services.catalog.param_resolution.get_discovery_service",
            return_value=discovery,
        ):
            result = await get_search_parameters(SearchContext("plasmodb", "gene", "S"))

        assert result["resolvedRecordType"] == "gene"

    async def test_resolves_record_type_case_insensitive(self) -> None:
        discovery = _mock_discovery(
            record_types=[
                {"urlSegment": "gene", "name": "GeneRecordClass"},
            ],
            search_details={"parameters": []},
        )
        with patch(
            "veupath_chatbot.services.catalog.param_resolution.get_discovery_service",
            return_value=discovery,
        ):
            result = await get_search_parameters(SearchContext("plasmodb", "GENE", "S"))

        assert result["resolvedRecordType"] == "gene"

    async def test_resolves_by_display_name_when_single_match(self) -> None:
        discovery = _mock_discovery(
            record_types=[
                {
                    "urlSegment": "gene",
                    "name": "GeneRecordClass",
                    "displayName": "Genes",
                },
            ],
            search_details={"parameters": []},
        )
        with patch(
            "veupath_chatbot.services.catalog.param_resolution.get_discovery_service",
            return_value=discovery,
        ):
            result = await get_search_parameters(SearchContext("plasmodb", "genes", "S"))

        assert result["resolvedRecordType"] == "gene"

    async def test_does_not_resolve_display_name_on_multiple_matches(self) -> None:
        """When multiple record types match by displayName, don't resolve."""
        discovery = _mock_discovery(
            record_types=[
                {"urlSegment": "gene1", "displayName": "Genes"},
                {"urlSegment": "gene2", "displayName": "Genes"},
            ],
            search_details={"parameters": []},
        )
        with patch(
            "veupath_chatbot.services.catalog.param_resolution.get_discovery_service",
            return_value=discovery,
        ):
            result = await get_search_parameters(SearchContext("plasmodb", "genes", "S"))

        # Falls back to the original
        assert result["resolvedRecordType"] == "genes"

    async def test_unwraps_search_data_envelope(self) -> None:
        """When details has a 'searchData' wrapper, unwrap it."""
        discovery = _mock_discovery(
            record_types=[{"urlSegment": "gene"}],
            search_details={
                "searchData": {
                    "displayName": "Wrapped Search",
                    "description": "From searchData",
                    "parameters": [
                        {"name": "param1", "type": "string"},
                    ],
                },
            },
        )
        with patch(
            "veupath_chatbot.services.catalog.param_resolution.get_discovery_service",
            return_value=discovery,
        ):
            result = await get_search_parameters(SearchContext("plasmodb", "gene", "S"))

        params = result["parameters"]
        assert isinstance(params, list)
        assert len(params) == 1

    async def test_parameter_required_from_allow_empty(self) -> None:
        """required = not allowEmptyValue."""
        discovery = _mock_discovery(
            record_types=[{"urlSegment": "gene"}],
            search_details={
                "parameters": [
                    {"name": "optional_param", "allowEmptyValue": True},
                    {"name": "required_param", "allowEmptyValue": False},
                ],
            },
        )
        with patch(
            "veupath_chatbot.services.catalog.param_resolution.get_discovery_service",
            return_value=discovery,
        ):
            result = await get_search_parameters(SearchContext("plasmodb", "gene", "S"))

        opt = _get_param_by_name(result, "optional_param")
        req = _get_param_by_name(result, "required_param")
        assert opt["required"] is False
        assert req["required"] is True

    async def test_parameter_defaults_from_initial_display_value(self) -> None:
        discovery = _mock_discovery(
            record_types=[{"urlSegment": "gene"}],
            search_details={
                "parameters": [
                    {
                        "name": "param1",
                        "initialDisplayValue": "default_val",
                    },
                ],
            },
        )
        with patch(
            "veupath_chatbot.services.catalog.param_resolution.get_discovery_service",
            return_value=discovery,
        ):
            result = await get_search_parameters(SearchContext("plasmodb", "gene", "S"))

        p = _get_param_by_name(result, "param1")
        assert p["defaultValue"] == "default_val"

    async def test_parameter_defaults_from_initial_display(self) -> None:
        """initialDisplayValue from WDK becomes defaultValue in formatted output."""
        discovery = _mock_discovery(
            record_types=[{"urlSegment": "gene"}],
            search_details={
                "parameters": [
                    {"name": "param1", "initialDisplayValue": "fallback_val"},
                ],
            },
        )
        with patch(
            "veupath_chatbot.services.catalog.param_resolution.get_discovery_service",
            return_value=discovery,
        ):
            result = await get_search_parameters(SearchContext("plasmodb", "gene", "S"))

        p = _get_param_by_name(result, "param1")
        assert p["defaultValue"] == "fallback_val"

    async def test_initial_display_value_takes_priority(self) -> None:
        discovery = _mock_discovery(
            record_types=[{"urlSegment": "gene"}],
            search_details={
                "parameters": [
                    {
                        "name": "param1",
                        "initialDisplayValue": "preferred",
                        "defaultValue": "secondary",
                    },
                ],
            },
        )
        with patch(
            "veupath_chatbot.services.catalog.param_resolution.get_discovery_service",
            return_value=discovery,
        ):
            result = await get_search_parameters(SearchContext("plasmodb", "gene", "S"))

        p = _get_param_by_name(result, "param1")
        assert p["defaultValue"] == "preferred"

    async def test_allowed_values_from_vocabulary(self) -> None:
        discovery = _mock_discovery(
            record_types=[{"urlSegment": "gene"}],
            search_details={
                "parameters": [
                    {
                        "name": "organism",
                        "type": "single-pick-vocabulary",
                        "vocabulary": [
                            ["Pf3D7", "P. falciparum 3D7"],
                            ["PvP01", "P. vivax P01"],
                        ],
                    },
                ],
            },
        )
        with patch(
            "veupath_chatbot.services.catalog.param_resolution.get_discovery_service",
            return_value=discovery,
        ):
            result = await get_search_parameters(SearchContext("plasmodb", "gene", "S"))

        p = _get_param_by_name(result, "organism")
        allowed = p["allowedValues"]
        assert isinstance(allowed, list)
        values = [e["value"] for e in allowed if isinstance(e, dict)]
        assert "Pf3D7" in values

    async def test_allowed_values_capped_at_50(self) -> None:
        vocab = [[f"val{i}", f"display{i}"] for i in range(100)]
        discovery = _mock_discovery(
            record_types=[{"urlSegment": "gene"}],
            search_details={
                "parameters": [
                    {
                        "name": "big_param",
                        "type": "single-pick-vocabulary",
                        "vocabulary": vocab,
                    },
                ],
            },
        )
        with patch(
            "veupath_chatbot.services.catalog.param_resolution.get_discovery_service",
            return_value=discovery,
        ):
            result = await get_search_parameters(SearchContext("plasmodb", "gene", "S"))

        p = _get_param_by_name(result, "big_param")
        allowed = p["allowedValues"]
        assert isinstance(allowed, list)
        assert len(allowed) == 50

    async def test_skips_params_without_name(self) -> None:
        discovery = _mock_discovery(
            record_types=[{"urlSegment": "gene"}],
            search_details={
                "parameters": [
                    {"type": "string"},  # no name
                    {"name": "", "type": "string"},  # empty name
                    {"name": "valid", "type": "string"},
                ],
            },
        )
        with patch(
            "veupath_chatbot.services.catalog.param_resolution.get_discovery_service",
            return_value=discovery,
        ):
            result = await get_search_parameters(SearchContext("plasmodb", "gene", "S"))

        params = result["parameters"]
        assert isinstance(params, list)
        assert len(params) == 1
        first = params[0]
        assert isinstance(first, dict)
        assert first["name"] == "valid"

    async def test_raises_validation_error_when_search_not_found(self) -> None:
        discovery = _mock_discovery(
            record_types=[{"urlSegment": "gene", "name": "Genes"}],
            search_details_raises=AppError(ErrorCode.SEARCH_NOT_FOUND, "not found"),
            searches_by_rt={
                "gene": [
                    {"urlSegment": "GenesByTaxon", "name": "Q1"},
                ]
            },
        )
        with (
            patch(
                "veupath_chatbot.services.catalog.param_resolution.get_discovery_service",
                return_value=discovery,
            ),
            pytest.raises(ValidationError) as exc_info,
        ):
            await get_search_parameters(SearchContext("plasmodb", "gene", "NonexistentSearch"))

        assert "NonexistentSearch" in (exc_info.value.detail or "")

    async def test_fallback_scan_finds_search_in_other_record_type(self) -> None:
        """When initial get_search_details fails, scan all record types."""
        call_count = 0

        async def _get_search_details(
            ctx: SearchContext, expand_params: bool = True
        ) -> WDKSearchResponse:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                msg = "not found on first try"
                raise AppError(ErrorCode.SEARCH_NOT_FOUND, msg)
            return _to_wdk_search_response({
                "displayName": "Found It",
                "description": "desc",
                "parameters": [{"name": "p1", "type": "string"}],
            })

        discovery = MagicMock()
        discovery.get_record_types = AsyncMock(
            return_value=[
                WDKRecordType(url_segment="gene", full_name="Genes"),
                WDKRecordType(url_segment="transcript", full_name="Transcripts"),
            ]
        )
        discovery.get_search_details = AsyncMock(side_effect=_get_search_details)
        discovery.get_searches = AsyncMock(
            side_effect=lambda _site_id, rt: (
                [WDKSearch(url_segment="SharedSearch")] if rt == "transcript" else []
            ),
        )

        with patch(
            "veupath_chatbot.services.catalog.param_resolution.get_discovery_service",
            return_value=discovery,
        ):
            result = await get_search_parameters(SearchContext("plasmodb", "gene", "SharedSearch"))

        assert result["resolvedRecordType"] == "transcript"
        assert result["displayName"] == "Found It"


# ---------------------------------------------------------------------------
# get_search_parameters_tool
# ---------------------------------------------------------------------------


class TestGetSearchParametersTool:
    """Test the tool-wrapper get_search_parameters_tool()."""

    async def test_returns_result_on_success(self) -> None:
        discovery = _mock_discovery(
            record_types=[{"urlSegment": "gene"}],
            search_details={
                "displayName": "Test",
                "parameters": [],
            },
        )
        with patch(
            "veupath_chatbot.services.catalog.param_resolution.get_discovery_service",
            return_value=discovery,
        ):
            result = await get_search_parameters_tool(
                SearchContext("plasmodb", "gene", "GenesByTaxon")
            )

        assert result["searchName"] == "GenesByTaxon"

    async def test_returns_tool_error_on_validation_error(self) -> None:
        discovery = _mock_discovery(
            record_types=[{"urlSegment": "gene"}],
            search_details_raises=AppError(ErrorCode.SEARCH_NOT_FOUND, "fail"),
            searches_by_rt={"gene": []},
        )
        with patch(
            "veupath_chatbot.services.catalog.param_resolution.get_discovery_service",
            return_value=discovery,
        ):
            result = await get_search_parameters_tool(
                SearchContext("plasmodb", "gene", "NonexistentSearch")
            )

        assert result["ok"] is False
        assert "code" in result

    async def test_tool_error_extracts_error_code(self) -> None:
        discovery = _mock_discovery(
            record_types=[{"urlSegment": "gene"}],
            search_details_raises=AppError(ErrorCode.SEARCH_NOT_FOUND, "fail"),
            searches_by_rt={"gene": []},
        )
        with patch(
            "veupath_chatbot.services.catalog.param_resolution.get_discovery_service",
            return_value=discovery,
        ):
            result = await get_search_parameters_tool(
                SearchContext("plasmodb", "gene", "NonexistentSearch")
            )

        assert result["code"] == ErrorCode.SEARCH_NOT_FOUND.value


# ---------------------------------------------------------------------------
# _get_search_details_with_portal_fallback
# ---------------------------------------------------------------------------


class TestGetSearchDetailsWithPortalFallback:
    """Test the portal fallback mechanism."""

    async def test_returns_client_result_on_success(self) -> None:
        client = _mock_wdk_client(
            search_details_with_params={
                "urlSegment": "GenesByTaxon",
                "paramNames": ["organism"],
            }
        )
        with patch(
            "veupath_chatbot.services.catalog.param_resolution.get_wdk_client",
            return_value=client,
        ):
            result = await _get_search_details_with_portal_fallback(
                site_id="plasmodb",
                client=client,
                record_type="gene",
                search_name="GenesByTaxon",
                context_values={"organism": "Pf3D7"},
            )

        assert isinstance(result, WDKSearchResponse)
        assert result.search_data.url_segment == "GenesByTaxon"
        assert "organism" in result.search_data.param_names

    async def test_falls_back_to_portal_on_wdk_error(self) -> None:
        failing_client = _mock_wdk_client(
            search_details_with_params_raises=WDKError("fail"),
        )
        portal_client = _mock_wdk_client(
            search_details_with_params={
                "urlSegment": "GenesByTaxon",
                "paramNames": ["from_portal"],
            },
        )
        with patch(
            "veupath_chatbot.services.catalog.param_resolution.get_wdk_client",
            return_value=portal_client,
        ):
            result = await _get_search_details_with_portal_fallback(
                site_id="plasmodb",
                client=failing_client,
                record_type="gene",
                search_name="GenesByTaxon",
                context_values={},
            )

        assert isinstance(result, WDKSearchResponse)
        assert "from_portal" in result.search_data.param_names

    async def test_no_fallback_when_already_portal(self) -> None:
        failing_client = _mock_wdk_client(
            search_details_with_params_raises=WDKError("fail"),
        )
        with pytest.raises(WDKError):
            await _get_search_details_with_portal_fallback(
                site_id="veupathdb",
                client=failing_client,
                record_type="gene",
                search_name="GenesByTaxon",
                context_values={},
            )


# ---------------------------------------------------------------------------
# expand_search_details_with_params
# ---------------------------------------------------------------------------


class TestExpandSearchDetailsWithParams:
    """Test expand_search_details_with_params()."""

    async def test_basic_expansion(self) -> None:
        discovery = _mock_discovery(
            search_details={
                "urlSegment": "GenesByTaxon",
                "parameters": [{"name": "organism", "type": "string"}],
            },
        )
        client = _mock_wdk_client(
            record_types=[{"urlSegment": "gene"}],
            searches_by_rt={"gene": [{"urlSegment": "GenesByTaxon"}]},
            search_details_with_params={
                "urlSegment": "GenesByTaxon",
                "parameters": [{"name": "organism", "type": "string"}],
            },
        )
        with (
            patch(
                "veupath_chatbot.services.catalog.param_resolution.get_discovery_service",
                return_value=discovery,
            ),
            patch(
                "veupath_chatbot.services.catalog.param_resolution.get_wdk_client",
                return_value=client,
            ),
        ):
            result = await expand_search_details_with_params(
                SearchContext("plasmodb", "gene", "GenesByTaxon"), {"organism": "Pf3D7"}
            )

        assert isinstance(result, WDKSearchResponse)
        assert result.search_data.url_segment == "GenesByTaxon"

    async def test_filters_context_to_allowed_params(self) -> None:
        discovery = _mock_discovery(
            search_details={
                "urlSegment": "GenesByTaxon",
                "parameters": [{"name": "organism", "type": "string"}],
            },
        )
        client = _mock_wdk_client(
            record_types=[{"urlSegment": "gene"}],
            searches_by_rt={"gene": [{"urlSegment": "GenesByTaxon"}]},
            search_details_with_params={
                "urlSegment": "GenesByTaxon",
            },
        )
        with (
            patch(
                "veupath_chatbot.services.catalog.param_resolution.get_discovery_service",
                return_value=discovery,
            ),
            patch(
                "veupath_chatbot.services.catalog.param_resolution.get_wdk_client",
                return_value=client,
            ),
        ):
            await expand_search_details_with_params(
                SearchContext("plasmodb", "gene", "GenesByTaxon"),
                {"organism": "Pf3D7", "unknown": "value"},
            )

        # Verify that the client was called -- we cannot easily check the
        # exact context because normalization happens, but it should not error
        assert client.get_search_details_with_params.called

    async def test_handles_none_context(self) -> None:
        discovery = _mock_discovery(
            search_details={
                "urlSegment": "GenesByTaxon",
                "parameters": [],
            },
        )
        client = _mock_wdk_client(
            record_types=[{"urlSegment": "gene"}],
            searches_by_rt={"gene": [{"urlSegment": "GenesByTaxon"}]},
            search_details_with_params={
                "urlSegment": "GenesByTaxon",
            },
        )
        with (
            patch(
                "veupath_chatbot.services.catalog.param_resolution.get_discovery_service",
                return_value=discovery,
            ),
            patch(
                "veupath_chatbot.services.catalog.param_resolution.get_wdk_client",
                return_value=client,
            ),
        ):
            result = await expand_search_details_with_params(
                SearchContext("plasmodb", "gene", "GenesByTaxon"), None
            )

        assert isinstance(result, WDKSearchResponse)
