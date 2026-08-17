"""A context WDK cannot narrow by still yields the search's parameters.

Narrowing is an enrichment. When WDK refuses it, the static view is the answer,
because a search with no parameters is a different claim from one we could not
narrow.
"""

from __future__ import annotations

from typing import cast

import pytest
from pydantic import JsonValue

from pathfinder.domain.parameters.values import ParamValue, SinglePickValue
from pathfinder.domain.search import SearchContext
from pathfinder.integrations.veupathdb.wdk_models import (
    StepValidation,
    WDKSearch,
    WDKSearchResponse,
)
from pathfinder.integrations.veupathdb.wdk_parameters import WDKEnumParam, WDKParameter
from pathfinder.platform.errors import WDKError
from pathfinder.platform.types import JSONObject
from pathfinder.services.catalog import param_resolution as pr

_CTX = SearchContext(
    site_id="plasmodb",
    record_type="transcript",
    search_name="GenesByOrthologPattern",
)
_MAPS = ("phyletic_indent_map", "phyletic_term_map")
_PARAMS = ("profile_pattern", "organism", *_MAPS)
_WDK_500 = "Server error '500 Internal Server Error'"


def _param(name: str) -> WDKParameter:
    raw: JSONObject = {
        "type": "multi-pick-vocabulary",
        "name": name,
        "display_name": name,
        "vocabulary": cast(
            "JsonValue",
            [["Plasmodium falciparum 3D7", "P. falciparum 3D7", None]],
        ),
        "allow_empty_value": False,
    }
    return cast("WDKParameter", WDKEnumParam.model_validate(raw))


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


def _response() -> WDKSearchResponse:
    parameters = [_param(n) for n in ("profile_pattern", "organism")]
    parameters += [_hidden_map(n) for n in _MAPS]
    return WDKSearchResponse(
        search_data=WDKSearch(
            url_segment=_CTX.search_name,
            full_name=_CTX.search_name,
            display_name="Orthology Phylogenetic Profile",
            param_names=list(_PARAMS),
            parameters=parameters,
        ),
        validation=StepValidation(),
    )


class _Client:
    """Answers the static view and refuses to narrow, the way WDK does."""

    def __init__(self, *, contextual_fails: bool) -> None:
        self._contextual_fails = contextual_fails
        self.static_calls = 0
        self.contextual_calls = 0
        self.contexts: list[dict[str, str]] = []

    async def get_search_details(
        self, record_type: str, search_name: str, *, expand_params: bool = True
    ) -> WDKSearchResponse:
        del record_type, search_name, expand_params
        self.static_calls += 1
        return _response()

    async def get_search_details_with_params(
        self,
        record_type: str,
        search_name: str,
        context: dict[str, str],
        *,
        expand_params: bool = True,
    ) -> WDKSearchResponse:
        del record_type, search_name, expand_params
        self.contextual_calls += 1
        self.contexts.append(dict(context))
        if self._contextual_fails:
            raise WDKError(_WDK_500, status=500)
        return _response()


def _context() -> dict[str, ParamValue]:
    return {"organism": SinglePickValue(value="Plasmodium falciparum 3D7")}


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> _Client:
    stub = _Client(contextual_fails=True)
    monkeypatch.setattr(pr, "get_wdk_client", lambda site_id: stub)

    async def _record_type(ctx: SearchContext) -> str:
        return ctx.record_type

    async def _discovery(
        ctx: SearchContext,
    ) -> tuple[WDKSearchResponse, set[str]]:
        del ctx
        return _response(), set(_PARAMS)

    monkeypatch.setattr(pr, "find_record_type_for_search", _record_type)
    monkeypatch.setattr(pr, "_load_discovery_details_and_allowed", _discovery)
    return stub


class TestARefusalToNarrowKeepsTheParameters:
    @pytest.mark.asyncio
    async def test_the_parameters_still_come_back(self, client: _Client) -> None:
        response = await pr.expand_search_details_with_params(_CTX, _context())

        assert [p.name for p in response.search_data.parameters or []] == list(_PARAMS)

    @pytest.mark.asyncio
    async def test_it_does_not_raise(self, client: _Client) -> None:
        assert await pr.expand_search_details_with_params(_CTX, _context()) is not None

    @pytest.mark.asyncio
    async def test_the_static_view_is_what_answers(self, client: _Client) -> None:
        await pr.expand_search_details_with_params(_CTX, _context())

        assert client.contextual_calls >= 1
        assert client.static_calls == 1


class TestNarrowingIsStillPreferred:
    @pytest.mark.asyncio
    async def test_the_static_view_is_not_asked_for_when_wdk_narrows(
        self, client: _Client, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        willing = _Client(contextual_fails=False)
        monkeypatch.setattr(pr, "get_wdk_client", lambda site_id: willing)

        await pr.expand_search_details_with_params(_CTX, _context())

        assert willing.contextual_calls == 1
        assert willing.static_calls == 0

    @pytest.mark.asyncio
    async def test_the_hidden_structural_params_are_sent(
        self, client: _Client, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # WDK answers 500 to a phyletic read whose context omits either map.
        willing = _Client(contextual_fails=False)
        monkeypatch.setattr(pr, "get_wdk_client", lambda site_id: willing)

        await pr.expand_search_details_with_params(_CTX, _context())

        assert willing.contexts[0] == {
            "organism": '["Plasmodium falciparum 3D7"]',
            "phyletic_indent_map": "[]",
            "phyletic_term_map": "[]",
        }
