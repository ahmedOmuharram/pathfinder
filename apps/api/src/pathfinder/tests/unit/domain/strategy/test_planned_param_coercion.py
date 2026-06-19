"""PlannedParameter self-heals scalar value/param_type mismatches.

WDK is stringly-typed (numeric params are StringParam). An in-place mutation
elsewhere can leave a param with ``param_type='string'`` but a NumberValue.
The model-level validator coerces scalar mismatches instead of rejecting, so
construction (including LangGraph checkpoint reload via ``StrategyPlan(**dump)``)
never crashes on a benign, coercible mismatch. Structural mismatches still raise.
"""

from __future__ import annotations

import pytest

from pathfinder.domain.parameters.values import MultiPickValue, NumberValue
from pathfinder.domain.strategy.plan import (
    ParamStatus,
    PlannedParameter,
    PlannedStep,
    StepStatus,
    StepType,
    StrategyPlan,
)


def test_scalar_mismatch_is_coerced_not_rejected() -> None:
    param = PlannedParameter(
        name="fold_change",
        display_name="fold_change",
        param_type="string",
        value=NumberValue(value=2.0),
        status=ParamStatus.SET,
        required=True,
    )
    assert param.value is not None
    assert param.value.type == "string"
    assert param.value.value == "2"


def test_structural_mismatch_still_raises() -> None:
    with pytest.raises(ValueError, match="fold_change"):
        PlannedParameter(
            name="fold_change",
            display_name="fold_change",
            param_type="string",
            value=MultiPickValue(values=["a", "b"]),
            status=ParamStatus.SET,
            required=True,
        )


def test_plan_round_trips_through_dump_with_mismatch() -> None:
    # Simulate a checkpoint whose stored param has a coercible mismatch:
    # rebuilding from the dumped dict must NOT raise (it self-heals).
    plan = StrategyPlan(
        title="t",
        description="d",
        rationale="r",
        steps=[
            PlannedStep(
                id="s1",
                search_name="X",
                display_name="X",
                step_type=StepType.LEAF,
                status=StepStatus.READY,
                parameters=[
                    PlannedParameter(
                        name="fold_change",
                        display_name="fold_change",
                        param_type="string",
                        value=NumberValue(value=2.0),
                        status=ParamStatus.SET,
                        required=True,
                    ),
                ],
            ),
        ],
        connections=[],
    )
    dumped = plan.model_dump()
    # Force the stored value back into a number shape (the corruption).
    dumped["steps"][0]["parameters"][0]["value"] = {"type": "number", "value": 2.0}
    rebuilt = StrategyPlan(**dumped)
    assert rebuilt.steps[0].parameters[0].value is not None
    assert rebuilt.steps[0].parameters[0].value.type == "string"
