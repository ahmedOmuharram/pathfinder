from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from pathfinder.ai.agents._instructions import pinned_active_plan
from pathfinder.ai.agents.state import AgentToolState
from pathfinder.domain.strategy.plan import (
    PlannedStep,
    PlanStatus,
    StepStatus,
    StepType,
    StrategyPlan,
)


def _plan(status: PlanStatus) -> StrategyPlan:
    return StrategyPlan(
        id="plan_pin01",
        title="Pinned",
        description="d",
        rationale="r",
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


def _ctx(plan: StrategyPlan | None) -> Any:
    ctx = MagicMock()
    ctx.deps = MagicMock()
    state = AgentToolState()
    state.active_plan = plan
    ctx.deps.agent_state = state
    return ctx


def test_none_when_no_plan() -> None:
    assert pinned_active_plan(_ctx(None)) is None


def test_none_when_failed() -> None:
    assert pinned_active_plan(_ctx(_plan(PlanStatus.FAILED))) is None


@pytest.mark.parametrize(
    "status",
    [
        PlanStatus.DRAFT,
        PlanStatus.PRESENTED,
        PlanStatus.APPROVED,
        PlanStatus.EXECUTING,
        PlanStatus.COMPLETE,
    ],
)
def test_renders_for_non_failed(status: PlanStatus) -> None:
    out = pinned_active_plan(_ctx(_plan(status)))
    assert out is not None
    assert "plan_pin01" in out
    assert status.value in out
    assert "DO NOT call `create_plan`" in out
