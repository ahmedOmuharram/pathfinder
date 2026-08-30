"""An organism substitution comes back with the dependents it invalidated.

Re-binding a criterion with the values it already held plus a new organism
cannot copy a dependent value forward: that value names an entry of the old
organism's vocabulary. ``set_criterion`` hands the dependent back to be decided.
"""

from __future__ import annotations

from collections.abc import Callable
from unittest.mock import MagicMock

import pytest
from pydantic_ai import ModelRetry

from pathfinder.ai.agents.state import AgentToolState
from pathfinder.ai.tools.standalone import frame_spec
from pathfinder.ai.tools.standalone.frame_spec import (
    ParamProposals,
    SetCriterionResult,
    set_criterion,
)
from pathfinder.domain.parameters.wdk_vocab import VocabOption
from pathfinder.domain.search import SearchContext
from pathfinder.domain.strategy.validation import StepValidation
from pathfinder.integrations.veupathdb.wdk_models import WDKSearch, WDKSearchResponse
from pathfinder.services.catalog import param_discovery, searches
from pathfinder.services.catalog.param_dag import ParamFetcher
from pathfinder.services.catalog.param_formatting import ParameterInfo
from pathfinder.services.catalog.param_validation import ValidatedParams

_PF = "Plasmodium falciparum 3D7"
_PV = "Plasmodium vivax P01"
_DERISI = "DeRisi 3D7 Smoothed"
_ZHU = "Zhu P01 time course"

ParamsAt = Callable[[dict[str, str]], list[ParameterInfo]]


def _organism() -> ParameterInfo:
    return ParameterInfo(
        name="organism",
        display_name="organism",
        type="multi-pick-vocabulary",
        required=True,
        is_visible=True,
        help="",
        value_format="",
        vocab_leaves=[
            VocabOption(value=_PF, display="P. falciparum 3D7"),
            VocabOption(value=_PV, display="P. vivax P01"),
        ],
    )


def _profileset(options: list[VocabOption], default: str) -> ParameterInfo:
    return ParameterInfo(
        name="profileset",
        display_name="profileset",
        type="single-pick-vocabulary",
        required=True,
        is_visible=True,
        help="",
        value_format="",
        default_value=default,
        allowed_values=options,
        vocab_depends_on=["organism"],
    )


def _profilesets_under_organism(context: dict[str, str]) -> list[ParameterInfo]:
    if _PV in context.get("organism", ""):
        return [
            _organism(),
            _profileset([VocabOption(value=_ZHU, display="Zhu P01")], _ZHU),
        ]
    return [
        _organism(),
        _profileset(
            [
                VocabOption(value=_DERISI, display=_DERISI),
                VocabOption(value="Su 3D7 strand-specific", display="Su 3D7"),
            ],
            _DERISI,
        ),
    ]


def _serve(monkeypatch: pytest.MonkeyPatch, at: ParamsAt) -> None:
    """Serve one search's parameters, its definition and a passing validation."""

    def _fetch_at(*_args: object) -> ParamFetcher:
        async def fetch_at(context: dict[str, str]) -> list[ParameterInfo]:
            return at(context)

        return fetch_at

    monkeypatch.setattr(frame_spec, "wdk_fetch_at", _fetch_at)

    async def _definition(
        record_type: str, name: str, *, expand_params: bool = True
    ) -> WDKSearchResponse:
        del record_type, expand_params
        return WDKSearchResponse(
            searchData=WDKSearch(urlSegment=name),
            validation=StepValidation(level="NONE", is_valid=False),
        )

    client = MagicMock()
    client.get_search_details = _definition
    monkeypatch.setattr(searches, "get_wdk_client", lambda _site: client)

    async def _details(
        ctx: SearchContext, **_kw: object
    ) -> tuple[WDKSearchResponse, str]:
        return (
            WDKSearchResponse(
                searchData=WDKSearch(urlSegment=ctx.search_name),
                validation=StepValidation(level="NONE", is_valid=False),
            ),
            "etag",
        )

    monkeypatch.setattr(param_discovery, "fetch_search_details", _details)
    monkeypatch.setattr(frame_spec, "fetch_search_details", _details)

    async def _validate(*_args: object, **_kwargs: object) -> ValidatedParams:
        return ValidatedParams()

    monkeypatch.setattr(frame_spec, "validate_parameters", _validate)


def _ctx(state: AgentToolState) -> MagicMock:
    ctx = MagicMock()
    ctx.tool_call_id = "call_1"
    ctx.deps.agent_state = state
    ctx.deps.site_id = "plasmodb"
    graph = MagicMock()
    graph.record_type = "transcript"
    ctx.deps.strategy_session.get_graph.return_value = graph
    return ctx


async def _bind(state: AgentToolState, params: ParamProposals) -> SetCriterionResult:
    return (
        await set_criterion(
            _ctx(state),
            criterion_id="step_expr",
            text="expression profile of the protease genes",
            search_name="GenesByProfile",
            params=params,
        )
    ).return_value


async def test_the_swap_hands_back_the_dependent_it_invalidated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _serve(monkeypatch, _profilesets_under_organism)
    state = AgentToolState()

    result = await _bind(state, {"organism": [_PV], "profileset": _DERISI})

    assert [entry.name for entry in result.redecide] == ["profileset"]
    assert [o.value for o in result.redecide[0].vocabulary] == [_ZHU]
    assert state.operational_spec_draft.criteria == [], "nothing is recorded yet"


async def test_the_fresh_value_binds_and_the_other_params_are_copied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _serve(monkeypatch, _profilesets_under_organism)
    state = AgentToolState()

    await _bind(state, {"organism": [_PV], "profileset": _DERISI})
    result = await _bind(state, {"organism": [_PV], "profileset": _ZHU})

    assert result.redecide == []
    assert result.resolved_params["profileset"] == _ZHU
    assert result.resolved_params["organism"] == f'["{_PV}"]'
    assert state.operational_spec_draft.criteria[0].id == "step_expr"


async def test_the_old_organisms_value_is_refused_on_the_re_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A second pass that copies the stale value forward is a retry, not a bind."""
    _serve(monkeypatch, _profilesets_under_organism)
    state = AgentToolState()

    await _bind(state, {"organism": [_PV], "profileset": _DERISI})
    with pytest.raises(ModelRetry) as excinfo:
        await _bind(state, {"organism": [_PV], "profileset": _DERISI})

    message = str(excinfo.value)
    assert "profileset" in message
    assert _ZHU in message
    assert state.operational_spec_draft.criteria == []


async def test_an_unchanged_organism_re_binds_without_a_redecide(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Re-stating the same values changes nothing and asks nothing."""
    _serve(monkeypatch, _profilesets_under_organism)
    state = AgentToolState()

    result = await _bind(state, {"organism": [_PF], "profileset": _DERISI})

    assert result.redecide == []
    assert result.resolved_params["profileset"] == _DERISI
