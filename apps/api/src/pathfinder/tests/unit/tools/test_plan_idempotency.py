from __future__ import annotations

from collections.abc import Iterable
from typing import Any
from unittest.mock import MagicMock

import pytest
from pydantic_ai.exceptions import ModelRetry

from pathfinder.ai.agents.state import AgentToolState
from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.tools.standalone._plan_models import PlannedStepInput
from pathfinder.ai.tools.standalone.plan import create_plan
from pathfinder.domain.parameters.specs import ParamSpecNormalized
from pathfinder.domain.parameters.values import MultiPickValue
from pathfinder.domain.parameters.wdk_vocab import WDKVocabTerm
from pathfinder.domain.strategy.plan import (
    PlannedStep,
    PlanStatus,
    StepStatus,
    StepType,
    StrategyPlan,
)
from pathfinder.domain.strategy.session import StrategySession
from pathfinder.platform.tool_errors import ToolErrorPayload

_ORG_SPEC = ParamSpecNormalized(
    name="organism",
    param_type="multi-pick-vocabulary",
    vocabulary=[
        WDKVocabTerm(("Plasmodium falciparum 3D7", "P. falciparum 3D7", None)),
    ],
    allow_empty_value=False,
)


@pytest.fixture(autouse=True)
def _stub_fetch_specs_by_search(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _stub(
        site_id: str,
        steps: Iterable[PlannedStepInput],
    ) -> dict[str, dict[str, ParamSpecNormalized]]:
        del site_id
        out: dict[str, dict[str, ParamSpecNormalized]] = {}
        for step in steps:
            if step.step_type == StepType.COMBINE or not step.search_name:
                continue
            out[step.search_name] = {"organism": _ORG_SPEC}
        return out

    monkeypatch.setattr(
        "pathfinder.ai.tools.standalone.plan._fetch_specs_by_search",
        _stub,
    )


def _deps(existing: StrategyPlan | None = None) -> AgentDeps:
    session = StrategySession(site_id="plasmodb")
    state = AgentToolState()
    if existing is not None:
        state.active_plan = existing
    return AgentDeps(
        site_id="plasmodb",
        strategy_session=session,
        agent_state=state,
    )


def _ctx(deps: AgentDeps) -> Any:
    ctx = MagicMock()
    ctx.deps = deps
    return ctx


def _plan(status: PlanStatus) -> StrategyPlan:
    return StrategyPlan(
        id="plan_existing01",
        title="Existing",
        description="x",
        rationale="x",
        status=status,
        steps=[
            PlannedStep(
                id="s1",
                search_name="GenesByTaxon",
                display_name="X",
                step_type=StepType.LEAF,
                status=StepStatus.READY,
            ),
        ],
        connections=[],
    )


def _leaf() -> PlannedStepInput:
    return PlannedStepInput(
        id="new_a",
        search_name="GenesByTaxon",
        display_name="New",
        step_type=StepType.LEAF,
        parameters={
            "organism": MultiPickValue(values=["Plasmodium falciparum 3D7"]),
        },
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    [PlanStatus.APPROVED, PlanStatus.EXECUTING, PlanStatus.COMPLETE],
)
async def test_create_plan_rejects_when_plan_locked(status: PlanStatus) -> None:
    deps = _deps(existing=_plan(status))
    with pytest.raises(ModelRetry) as excinfo:
        await create_plan(
            _ctx(deps),
            title="Re-create",
            description="d",
            rationale="r",
            steps=[_leaf()],
        )
    msg = str(excinfo.value)
    assert "PLAN_ALREADY_EXISTS" in msg
    assert "plan_existing01" in msg
    assert deps.agent_state.active_plan is not None
    assert deps.agent_state.active_plan.id == "plan_existing01"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    [PlanStatus.DRAFT, PlanStatus.PRESENTED, PlanStatus.FAILED],
)
async def test_create_plan_allowed_when_plan_unlocked(status: PlanStatus) -> None:
    deps = _deps(existing=_plan(status))
    result = await create_plan(
        _ctx(deps),
        title="Re-create",
        description="d",
        rationale="r",
        steps=[_leaf()],
    )
    assert not isinstance(result, ToolErrorPayload), (
        f"unexpected error on status={status}: {getattr(result, 'message', result)!r}"
    )
    assert deps.agent_state.active_plan is not None
    assert deps.agent_state.active_plan.id != "plan_existing01"


@pytest.mark.asyncio
async def test_create_plan_allowed_when_no_existing() -> None:
    deps = _deps(existing=None)
    result = await create_plan(
        _ctx(deps),
        title="Fresh",
        description="d",
        rationale="r",
        steps=[_leaf()],
    )
    assert not isinstance(result, ToolErrorPayload)
    assert deps.agent_state.active_plan is not None
