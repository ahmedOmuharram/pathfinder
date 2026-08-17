"""The phyletic search gets a contextual verdict instead of the static fallback.

``GenesByOrthologPattern`` answers 500 to a contextual read whose context omits
``phyletic_indent_map`` or ``phyletic_term_map``. The fake client below refuses
the same way, so a read that reaches WDK proves the structural params are sent.
"""

from __future__ import annotations

from typing import cast

import pytest
from pydantic import JsonValue

from pathfinder.domain.parameters.values import (
    MultiPickValue,
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
from pathfinder.platform.errors import WDKError
from pathfinder.platform.types import JSONObject
from pathfinder.services.catalog import param_validation as pv

_CTX = SearchContext(
    site_id="plasmodb",
    record_type="transcript",
    search_name="GenesByOrthologPattern",
)
_STRAIN = "Plasmodium falciparum 3D7"
_PATTERN = "%hsap:N%pfal:Y%"
_STRUCTURAL = ("phyletic_indent_map", "phyletic_term_map")
_WDK_500 = "Internal Error"


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


def _organism(initial: str) -> WDKParameter:
    raw: JSONObject = {
        "type": "multi-pick-vocabulary",
        "name": "organism",
        "display_name": "Organism",
        "display_type": "treeBox",
        "allow_empty_value": False,
        "initial_display_value": initial,
        "vocabulary": cast("JsonValue", [[_STRAIN, _STRAIN, None]]),
    }
    return cast("WDKParameter", WDKEnumParam.model_validate(raw))


def _parameters(*, pattern: str, organism_initial: str) -> list[WDKParameter]:
    profile_pattern = WDKStringParam(
        name="profile_pattern",
        display_name="profile_pattern",
        is_visible=False,
        allow_empty_value=False,
        initial_display_value=pattern,
    )
    species_lists = [
        WDKStringParam(
            name=name,
            display_name=name,
            allow_empty_value=True,
            initial_display_value=initial,
        )
        for name, initial in (
            ("included_species", "pfal"),
            ("excluded_species", "hsap"),
        )
    ]
    return [
        profile_pattern,
        *species_lists,
        *(_hidden_map(name) for name in _STRUCTURAL),
        _organism(organism_initial),
    ]


def _search_response(parameters: list[WDKParameter]) -> WDKSearchResponse:
    return WDKSearchResponse(
        search_data=WDKSearch(
            url_segment="GenesByOrthologPattern",
            full_name="GenesByOrthologPattern",
            display_name="Genes by ortholog pattern",
            param_names=[p.name for p in parameters],
            parameters=parameters,
        ),
        validation=StepValidation.model_validate(
            {"level": "SEMANTIC", "isValid": True}
        ),
    )


class _FakeWDK:
    """Answers the search-details endpoints the way live PlasmoDB does."""

    def __init__(self) -> None:
        self.contexts: list[dict[str, str]] = []

    async def get_search_details(
        self, record_type: str, search_name: str, *, expand_params: bool = True
    ) -> WDKSearchResponse:
        del record_type, search_name, expand_params
        # The published definition: the caller's values are absent.
        return _search_response(_parameters(pattern="hsap=1T", organism_initial="[]"))

    async def get_search_details_with_params(
        self,
        record_type: str,
        search_name: str,
        context: dict[str, str] | None = None,
        *,
        expand_params: bool = True,
    ) -> WDKSearchResponse:
        del record_type, search_name, expand_params
        sent = context or {}
        self.contexts.append(dict(sent))
        if any(name not in sent for name in _STRUCTURAL):
            raise WDKError(_WDK_500, status=500)
        return _search_response(
            _parameters(
                pattern=sent.get("profile_pattern", "hsap=1T"),
                organism_initial=sent.get("organism", "[]"),
            )
        )


class _FakeDiscovery:
    def __init__(self, client: _FakeWDK) -> None:
        self._client = client

    async def get_search_details(
        self, ctx: SearchContext, *, expand_params: bool = True
    ) -> WDKSearchResponse:
        return await self._client.get_search_details(
            ctx.record_type, ctx.search_name, expand_params=expand_params
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
def fake_wdk(monkeypatch: pytest.MonkeyPatch) -> _FakeWDK:
    client = _FakeWDK()
    monkeypatch.setattr(pv, "get_wdk_client", lambda site_id: client)
    monkeypatch.setattr(pv, "get_discovery_service", lambda: _FakeDiscovery(client))

    async def _no_refresh(
        ctx: SearchContext, *, parameter_name: str, context_values: JSONObject
    ) -> list[WDKParameter]:
        del ctx, parameter_name, context_values
        return []

    monkeypatch.setattr(pv, "get_refreshed_dependent_params", _no_refresh)
    return client


async def _validate() -> pv.ValidatedParams:
    return await pv.validate_parameters(
        _CTX,
        parameters={
            "profile_pattern": StringValue(value=_PATTERN),
            "included_species": StringValue(value="pfal"),
            "excluded_species": StringValue(value="hsap"),
            "organism": MultiPickValue(values=[_STRAIN]),
        },
        callbacks=_callbacks(),
    )


async def _resolve() -> pv.ResolvedSearch:
    return await pv._resolve_search_details(
        _CTX,
        resolved_record_type="transcript",
        parameters={
            "profile_pattern": StringValue(value=_PATTERN),
            "organism": MultiPickValue(values=[_STRAIN]),
        },
    )


class TestTheContextualReadHappens:
    @pytest.mark.asyncio
    async def test_wdk_read_the_callers_values(self, fake_wdk: _FakeWDK) -> None:
        del fake_wdk
        assert (await _resolve()).values_were_read is True

    @pytest.mark.asyncio
    async def test_the_structural_maps_are_sent(self, fake_wdk: _FakeWDK) -> None:
        await _validate()

        assert fake_wdk.contexts
        for context in fake_wdk.contexts:
            assert context["phyletic_indent_map"] == "[]"
            assert context["phyletic_term_map"] == "[]"

    @pytest.mark.asyncio
    async def test_the_callers_values_reach_wdk(self, fake_wdk: _FakeWDK) -> None:
        await _validate()

        assert fake_wdk.contexts[0]["profile_pattern"] == _PATTERN
        assert fake_wdk.contexts[0]["organism"] == f'["{_STRAIN}"]'

    @pytest.mark.asyncio
    async def test_nothing_is_reported_as_substituted(self, fake_wdk: _FakeWDK) -> None:
        del fake_wdk
        result = await _validate()

        assert result.substituted == []

    @pytest.mark.asyncio
    async def test_the_stated_values_survive(self, fake_wdk: _FakeWDK) -> None:
        del fake_wdk
        result = await _validate()

        assert result.params["profile_pattern"] == StringValue(value=_PATTERN)
        assert result.params["organism"] == MultiPickValue(values=[_STRAIN])


class TestAGenuine500StillFallsBack:
    @pytest.mark.asyncio
    async def test_the_static_definition_answers(
        self, fake_wdk: _FakeWDK, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def _always_500(
            record_type: str,
            search_name: str,
            context: dict[str, str] | None = None,
            *,
            expand_params: bool = True,
        ) -> WDKSearchResponse:
            del record_type, search_name, context, expand_params
            raise WDKError(_WDK_500, status=500)

        monkeypatch.setattr(fake_wdk, "get_search_details_with_params", _always_500)

        resolved = await _resolve()
        result = await _validate()

        assert resolved.values_were_read is False
        assert result.params["organism"] == MultiPickValue(values=[_STRAIN])
