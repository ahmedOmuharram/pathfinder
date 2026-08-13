"""A value the search defaulted is reported, not just applied."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from pathfinder.ai.agents.state import AgentToolState
from pathfinder.ai.tools.standalone import frame_spec
from pathfinder.domain.parameters.values import NumberValue, SinglePickValue
from pathfinder.services.catalog.param_dag import ResolvedParams
from pathfinder.services.catalog.param_intent import Provenance
from pathfinder.services.catalog.param_validation import ValidatedParams


def _ctx(state: AgentToolState) -> MagicMock:
    ctx = MagicMock()
    ctx.deps.agent_state = state
    ctx.deps.site_id = "plasmodb"
    ctx.deps.strategy_session.get_graph.return_value = None
    return ctx


def _resolved() -> ResolvedParams:
    return ResolvedParams(
        params={
            "organism": SinglePickValue(value="Plasmodium falciparum 3D7"),
            "min_expression_percentile": NumberValue(value=80),
        },
        provenance={
            "organism": Provenance.STATED,
            "min_expression_percentile": Provenance.DEFAULTED,
        },
    )


async def _bind(monkeypatch: pytest.MonkeyPatch, state: AgentToolState):
    async def _resolve(_ctx: object, **_kw: object) -> ResolvedParams:
        return _resolved()

    async def _validate(_ctx: object, **_kw: object) -> ValidatedParams:
        return ValidatedParams()

    monkeypatch.setattr(frame_spec, "resolve_search_params", _resolve)
    monkeypatch.setattr(frame_spec, "validate_parameters", _validate)
    return await frame_spec.set_criterion(
        _ctx(state),
        criterion_id="expression",
        text="top 10 percent of expression",
        search_name="GenesByMicroarray",
    )


class TestTheToolReportsWhatItDefaulted:
    @pytest.mark.asyncio
    async def test_a_defaulted_param_is_named(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        result = await _bind(monkeypatch, AgentToolState())

        assert result.defaulted_params == ["min_expression_percentile"]

    @pytest.mark.asyncio
    async def test_a_stated_param_is_not_named(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        result = await _bind(monkeypatch, AgentToolState())

        assert "organism" not in result.defaulted_params

    @pytest.mark.asyncio
    async def test_the_value_is_still_reported(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Naming the param is not enough; the reply has to state the value used.
        result = await _bind(monkeypatch, AgentToolState())

        assert result.resolved_params["min_expression_percentile"] == "80"


class TestTheSpecRemembers:
    @pytest.mark.asyncio
    async def test_the_criterion_carries_the_defaulted_names(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Later phases report to the user, so the spec has to keep this.
        state = AgentToolState()

        await _bind(monkeypatch, state)

        criterion = state.operational_spec_draft.criteria[0]
        assert criterion.defaulted_params == ["min_expression_percentile"]
