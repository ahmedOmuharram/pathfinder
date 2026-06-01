"""Stage A + F: submit_plan applies slot answers + refuses unresolved slots.

Tests the body-side resume path: pydantic-ai has emitted approval
request, the user filled the submit_plan card form, the next chat POST
carried both the ``approval-responded`` part and the
``data-plan-slot-answers`` payload. Backend extracted into
``state.plan_slot_answers``, ``build_node_deps`` resolved into
``deps.plan_slot_answers``. The body now applies the answers and either
sets the plan to APPROVED (success) or raises ModelRetry with
``UNRESOLVED_SLOTS`` (failure)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from pydantic_ai.exceptions import ModelRetry

from pathfinder.ai.agents.state import AgentToolState
from pathfinder.ai.graph.state import PlanSlotAnswer
from pathfinder.ai.tools.standalone.plan import submit_plan
from pathfinder.domain.parameters.values import SinglePickValue
from pathfinder.domain.strategy.plan import (
    ParamStatus,
    PlannedParameter,
    PlannedStep,
    PlanStatus,
    StepStatus,
    StepType,
    StrategyPlan,
    UserQuestion,
)


def _make_plan(
    *, params: list[PlannedParameter], questions: list[UserQuestion] | None = None
) -> StrategyPlan:
    step = PlannedStep(
        id="step_1",
        search_name="GenesByRNASeqFoldChange",
        display_name="Fold change",
        record_type="transcript",
        rationale="",
        step_type=StepType.LEAF,
        status=StepStatus.READY,
        parameters=params,
    )
    return StrategyPlan(
        title="P. falciparum gametocyte upregulated",
        description="",
        rationale="",
        status=PlanStatus.DRAFT,
        steps=[step],
        connections=[],
        questions=questions or [],
    )


def _ctx(deps: Any) -> Any:
    ctx = MagicMock()
    ctx.deps = deps
    return ctx


def _deps(plan: StrategyPlan, slot_answers: list[PlanSlotAnswer]) -> Any:
    deps = MagicMock()
    deps.agent_state = AgentToolState(active_plan=plan)
    deps.plan_slot_answers = slot_answers
    return deps


@pytest.mark.asyncio
async def test_submit_plan_applies_slot_answer_and_approves() -> None:
    """User filled the form for hard_floor; submit_plan body promotes
    the slot to USER_SET, copies the value, sets plan APPROVED."""
    plan = _make_plan(
        params=[
            PlannedParameter(
                name="hard_floor",
                display_name="Hard floor",
                param_type="single-pick-vocabulary",
                value=None,
                status=ParamStatus.NEEDS_USER_INPUT,
                required=True,
            ),
        ],
        questions=[
            UserQuestion(
                id="q_1",
                question="Pick a tier",
                related_step="step_1",
                related_param="hard_floor",
            ),
        ],
    )
    deps = _deps(
        plan,
        [PlanSlotAnswer(step_id="step_1", param_name="hard_floor", value="1693.23")],
    )
    result = await submit_plan(_ctx(deps))
    assert result.return_value.status == PlanStatus.APPROVED
    param = result.return_value.steps[0].parameters[0]
    assert param.value == SinglePickValue(value="1693.23")
    assert param.status == ParamStatus.USER_SET
    answered = result.return_value.questions[0].answer
    assert answered == "1693.23"


@pytest.mark.asyncio
async def test_submit_plan_refuses_when_user_input_unanswered() -> None:
    """A NEEDS_USER_INPUT slot with no matching answer in the approval
    payload triggers UNRESOLVED_SLOTS — the form was approved without
    being filled, which is a contract failure on the frontend."""
    plan = _make_plan(
        params=[
            PlannedParameter(
                name="hard_floor",
                display_name="Hard floor",
                param_type="single-pick-vocabulary",
                value=None,
                status=ParamStatus.NEEDS_USER_INPUT,
                required=True,
            ),
        ],
    )
    deps = _deps(plan, [])
    with pytest.raises(ModelRetry) as excinfo:
        await submit_plan(_ctx(deps))
    msg = str(excinfo.value)
    assert "UNRESOLVED_SLOTS" in msg
    assert "hard_floor" in msg
    assert plan.status == PlanStatus.DRAFT


@pytest.mark.asyncio
async def test_submit_plan_refuses_when_needs_discovery() -> None:
    """A NEEDS_DISCOVERY slot is not user-fillable — submit_plan must
    refuse and instruct the agent to route back to discovery instead of
    silently approving an incomplete plan."""
    plan = _make_plan(
        params=[
            PlannedParameter(
                name="samples_fc_comp_generic",
                display_name="Comparison samples",
                param_type="multi-pick-vocabulary",
                value=None,
                status=ParamStatus.NEEDS_DISCOVERY,
                required=True,
            ),
        ],
    )
    deps = _deps(plan, [])
    with pytest.raises(ModelRetry) as excinfo:
        await submit_plan(_ctx(deps))
    msg = str(excinfo.value)
    assert "UNRESOLVED_SLOTS" in msg
    assert "needs_discovery" in msg
    assert "samples_fc_comp_generic" in msg


@pytest.mark.asyncio
async def test_submit_plan_clean_plan_approves_without_slot_answers() -> None:
    """A plan with all SET parameters and no slots approves cleanly even
    when no slot_answers are provided."""
    plan = _make_plan(
        params=[
            PlannedParameter(
                name="hard_floor",
                display_name="Hard floor",
                param_type="single-pick-vocabulary",
                value=SinglePickValue(value="1693.23"),
                status=ParamStatus.SET,
                required=True,
            ),
        ],
    )
    deps = _deps(plan, [])
    result = await submit_plan(_ctx(deps))
    assert result.return_value.status == PlanStatus.APPROVED
