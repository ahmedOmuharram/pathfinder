from __future__ import annotations

import pytest
from pydantic_ai import ModelRetry

from pathfinder.ai.tools.standalone.plan import _validate_plan_against_wdk
from pathfinder.domain.strategy.plan import (
    ParamStatus,
    PlannedParameter,
    PlannedStep,
    StepStatus,
    StepType,
    StrategyPlan,
)

pytestmark = [pytest.mark.live_wdk, pytest.mark.asyncio]


def _single_leaf_plan(parameters: list[PlannedParameter]) -> StrategyPlan:
    return StrategyPlan(
        title="t",
        description="d",
        rationale="r",
        steps=[
            PlannedStep(
                id="leaf",
                search_name="GenesByText",
                display_name="Kinase",
                record_type="transcript",
                step_type=StepType.LEAF,
                status=StepStatus.READY,
                parameters=parameters,
            )
        ],
        connections=[],
    )


async def test_empty_params_leaf_rejected_at_planning(
    require_wdk_creds: None,
    wdk_session: None,
) -> None:
    del require_wdk_creds, wdk_session
    with pytest.raises(ModelRetry, match="text_expression"):
        await _validate_plan_against_wdk(_single_leaf_plan([]), "plasmodb")


async def test_leaf_with_explicit_unfilled_slot_not_rejected(
    require_wdk_creds: None,
    wdk_session: None,
) -> None:
    del require_wdk_creds, wdk_session
    slot = PlannedParameter(
        name="text_expression",
        display_name="Text expression",
        param_type="string",
        value=None,
        status=ParamStatus.NEEDS_USER_INPUT,
        required=True,
    )
    await _validate_plan_against_wdk(_single_leaf_plan([slot]), "plasmodb")
