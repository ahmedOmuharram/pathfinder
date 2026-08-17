"""A value the caller stated is never reported as a search default.

The phyletic search is the hard case: the contextual read fails, so WDK renders
the static definition, whose echoed values are the published defaults.
"""

from __future__ import annotations

from typing import cast

import pytest
from pydantic import JsonValue

from pathfinder.domain.parameters.values import (
    MultiPickValue,
    ParamValue,
    StringValue,
)
from pathfinder.domain.search import SearchContext
from pathfinder.integrations.veupathdb.wdk_models import (
    StepValidation,
    WDKSearch,
    WDKSearchResponse,
)
from pathfinder.integrations.veupathdb.wdk_parameters import (
    WDKEnumParam,
    WDKParameter,
    WDKStringParam,
)
from pathfinder.platform.errors import AppError, ErrorCode, ValidationError
from pathfinder.platform.types import JSONObject
from pathfinder.services.catalog import param_validation as pv

_CTX = SearchContext(
    site_id="plasmodb",
    record_type="transcript",
    search_name="GenesByOrthologPattern",
)
_STRAIN = "Plasmodium falciparum 3D7"


def _hidden_map(name: str) -> WDKParameter:
    raw: JSONObject = {
        "type": "multi-pick-vocabulary",
        "name": name,
        "display_name": name,
        "display_type": "checkBox",
        "is_visible": False,
        "allow_empty_value": True,
        "initial_display_value": "[]",
    }
    return cast("WDKParameter", WDKEnumParam.model_validate(raw))


def _parameters() -> list[WDKParameter]:
    profile_pattern = WDKStringParam(
        name="profile_pattern",
        display_name="profile_pattern",
        is_visible=False,
        allow_empty_value=False,
        initial_display_value="hsap=1T",
    )
    species_lists = [
        WDKStringParam(
            name=name,
            display_name=name,
            allow_empty_value=True,
            initial_display_value="",
        )
        for name in ("included_species", "excluded_species")
    ]
    organism_raw: JSONObject = {
        "type": "multi-pick-vocabulary",
        "name": "organism",
        "display_name": "Organism",
        "display_type": "treeBox",
        "allow_empty_value": False,
        "initial_display_value": "[]",
        "vocabulary": cast("JsonValue", [[_STRAIN, _STRAIN, None]]),
    }
    organism = cast("WDKParameter", WDKEnumParam.model_validate(organism_raw))
    return [
        profile_pattern,
        *species_lists,
        _hidden_map("phyletic_indent_map"),
        _hidden_map("phyletic_term_map"),
        organism,
    ]


def _definition(*, is_valid: bool) -> WDKSearchResponse:
    parameters = _parameters()
    errors = (
        None
        if is_valid
        else {"general": [], "byKey": {"organism": ["Cannot be empty."]}}
    )
    return WDKSearchResponse(
        search_data=WDKSearch(
            url_segment="GenesByOrthologPattern",
            full_name="GenesByOrthologPattern",
            display_name="Genes by ortholog pattern",
            param_names=[p.name for p in parameters],
            parameters=parameters,
        ),
        validation=StepValidation.model_validate(
            {"level": "DISPLAYABLE", "isValid": is_valid, "errors": errors}
        ),
    )


def _static_definition() -> pv.ResolvedSearch:
    return pv.ResolvedSearch(
        response=_definition(is_valid=True), values_were_read=False
    )


def _callbacks() -> pv.ValidationCallbacks:
    async def _resolve(
        record_type: str | None,
        search_name: str | None,
        *,
        require_match: bool = False,
        allow_fallback: bool = False,
    ) -> str | None:
        del search_name, require_match, allow_fallback
        return record_type

    async def _hint(search_name: str, record_type: str | None) -> str | None:
        del search_name, record_type
        return None

    return pv.ValidationCallbacks(
        resolve_record_type_for_search=_resolve, find_record_type_hint=_hint
    )


@pytest.fixture
def static_wdk(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_resolve(
        ctx: SearchContext,
        *,
        resolved_record_type: str,
        parameters: dict[str, ParamValue],
    ) -> pv.ResolvedSearch:
        del ctx, resolved_record_type, parameters
        return _static_definition()

    async def _no_refresh(
        ctx: SearchContext, *, parameter_name: str, context_values: JSONObject
    ) -> list[WDKParameter]:
        del ctx, parameter_name, context_values
        return []

    monkeypatch.setattr(pv, "_resolve_search_details", _fake_resolve)
    monkeypatch.setattr(pv, "get_refreshed_dependent_params", _no_refresh)


async def _validate() -> pv.ValidatedParams:
    return await pv.validate_parameters(
        _CTX,
        parameters={
            "profile_pattern": StringValue(value="%hsap:N%pfal:Y%"),
            "included_species": StringValue(value="pfal"),
            "excluded_species": StringValue(value="hsap"),
            "organism": MultiPickValue(values=[_STRAIN]),
        },
        callbacks=_callbacks(),
    )


class TestNothingTheCallerStatedIsADefault:
    @pytest.mark.asyncio
    async def test_a_derived_hidden_value_is_not_reported(
        self, static_wdk: None
    ) -> None:
        del static_wdk
        result = await _validate()

        assert "profile_pattern" not in result.substituted

    @pytest.mark.asyncio
    async def test_a_stated_organism_is_not_reported(self, static_wdk: None) -> None:
        del static_wdk
        result = await _validate()

        assert "organism" not in result.substituted

    @pytest.mark.asyncio
    async def test_a_structural_map_is_not_reported(self, static_wdk: None) -> None:
        del static_wdk
        # The two maps allow empty and carry the empty selection, so nothing
        # was filled and nothing was substituted.
        result = await _validate()

        assert result.substituted == []

    @pytest.mark.asyncio
    async def test_the_stated_values_survive(self, static_wdk: None) -> None:
        del static_wdk
        result = await _validate()

        assert result.params["profile_pattern"] == StringValue(value="%hsap:N%pfal:Y%")
        assert result.params["organism"] == MultiPickValue(values=[_STRAIN])


class _FailingContextualClient:
    """A WDK client whose contextual read answers 500."""

    async def get_search_details_with_params(
        self,
        record_type: str,
        search_name: str,
        *,
        context: dict[str, str],
        expand_params: bool = True,
    ) -> WDKSearchResponse:
        del record_type, search_name, context, expand_params
        raise AppError(ErrorCode.WDK_ERROR, "Internal Error", status=500)


class _PublishedDefinition:
    """A discovery service holding one non-contextual definition."""

    def __init__(self, response: WDKSearchResponse) -> None:
        self.response = response

    async def get_search_details(
        self, ctx: SearchContext, *, expand_params: bool = True
    ) -> WDKSearchResponse:
        del ctx, expand_params
        return self.response


def _serve(monkeypatch: pytest.MonkeyPatch, published: WDKSearchResponse) -> None:
    monkeypatch.setattr(
        pv, "get_wdk_client", lambda site_id: _FailingContextualClient()
    )
    monkeypatch.setattr(
        pv, "get_discovery_service", lambda: _PublishedDefinition(published)
    )


class TestAFallbackDefinitionCastsNoVerdict:
    """WDK judged no caller when the contextual read failed.

    The published definition carries the verdict on the empty parameter shape,
    which rejects every required parameter the caller in fact supplied.
    """

    @pytest.mark.asyncio
    async def test_a_rejection_in_the_fallback_does_not_raise(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _serve(monkeypatch, _definition(is_valid=False))

        result = await _validate()

        assert result.params["organism"] == MultiPickValue(values=[_STRAIN])

    @pytest.mark.asyncio
    async def test_a_contextual_rejection_still_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def _reject(
            ctx: SearchContext,
            *,
            resolved_record_type: str,
            parameters: dict[str, ParamValue],
        ) -> pv.ResolvedSearch:
            del ctx, resolved_record_type, parameters
            return pv.ResolvedSearch(
                response=_definition(is_valid=False), values_were_read=True
            )

        monkeypatch.setattr(pv, "_resolve_search_details", _reject)

        with pytest.raises(ValidationError, match="Invalid parameter value"):
            await _validate()
