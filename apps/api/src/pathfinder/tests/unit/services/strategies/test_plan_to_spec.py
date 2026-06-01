"""Unit tests for the ``plan_to_spec`` converter.

Stage E: ``build_step_tree_from_plan`` turns a fully-resolved plan into
a recursive ``StrategyStepNode`` tree that ``build_strategy_from_spec``
materializes WITHOUT going back through the LLM.
"""

from __future__ import annotations

import pytest

from pathfinder.domain.parameters.values import NumberValue, StringValue
from pathfinder.domain.strategy.plan import (
    ParamStatus,
    PlannedConnection,
    PlannedParameter,
    PlannedStep,
    PlanStatus,
    PlanTopologyError,
    StepStatus,
    StepType,
    StrategyPlan,
)
from pathfinder.services.strategies.plan_to_spec import (
    build_step_tree_from_plan,
)


def _leaf(
    step_id: str,
    *,
    search_name: str = "GenesByText",
    params: dict[str, str] | None = None,
) -> PlannedStep:
    parameters = [
        PlannedParameter(
            name=name,
            display_name=name,
            param_type="string",
            value=StringValue(value=value),
            status=ParamStatus.SET,
            required=True,
        )
        for name, value in (params or {}).items()
    ]
    return PlannedStep(
        id=step_id,
        search_name=search_name,
        display_name=step_id,
        record_type="transcript",
        rationale="",
        step_type=StepType.LEAF,
        status=StepStatus.READY,
        parameters=parameters,
    )


def _combine(step_id: str, *, operator: str = "INTERSECT") -> PlannedStep:
    return PlannedStep(
        id=step_id,
        search_name="__combine__",
        display_name=step_id,
        record_type="transcript",
        rationale="",
        step_type=StepType.COMBINE,
        status=StepStatus.READY,
        operator=operator,
    )


def _plan(steps: list[PlannedStep], conns: list[PlannedConnection]) -> StrategyPlan:
    return StrategyPlan(
        title="t",
        description="",
        rationale="",
        status=PlanStatus.APPROVED,
        steps=steps,
        connections=conns,
    )


def test_leaf_only_plan_yields_leaf_node() -> None:
    plan = _plan(
        steps=[_leaf("step_a", params={"q": "kinase"})],
        conns=[],
    )
    root = build_step_tree_from_plan(plan)
    assert root.search_name == "GenesByText"
    assert root.primary_input is None
    assert root.secondary_input is None
    assert root.parameters == {"q": StringValue(value="kinase")}


def test_combine_intersect_two_leaves() -> None:
    plan = _plan(
        steps=[
            _leaf("step_a", search_name="GenesByText", params={"q": "kinase"}),
            _leaf("step_b", search_name="GenesByGoTerm", params={"go": "GO:0001"}),
            _combine("step_c", operator="INTERSECT"),
        ],
        conns=[
            PlannedConnection(
                from_step="step_a",
                to_step="step_c",
                input_type="primary",
                operator="INTERSECT",
            ),
            PlannedConnection(
                from_step="step_b",
                to_step="step_c",
                input_type="secondary",
                operator="INTERSECT",
            ),
        ],
    )
    root = build_step_tree_from_plan(plan)
    assert root.search_name == "__combine__"
    assert root.primary_input is not None
    assert root.secondary_input is not None
    assert root.primary_input.search_name == "GenesByText"
    assert root.secondary_input.search_name == "GenesByGoTerm"


def test_unresolved_slot_blocks_conversion() -> None:
    step = PlannedStep(
        id="step_a",
        search_name="GenesByText",
        display_name="step_a",
        record_type="transcript",
        rationale="",
        step_type=StepType.LEAF,
        status=StepStatus.READY,
        parameters=[
            PlannedParameter(
                name="q",
                display_name="q",
                param_type="string",
                value=None,
                status=ParamStatus.NEEDS_USER_INPUT,
                required=True,
            ),
        ],
    )
    plan = _plan(steps=[step], conns=[])
    with pytest.raises(PlanTopologyError, match="unresolved slots"):
        build_step_tree_from_plan(plan)


def test_default_and_user_set_values_pass_through() -> None:
    step = PlannedStep(
        id="step_a",
        search_name="GenesByText",
        display_name="step_a",
        record_type="transcript",
        rationale="",
        step_type=StepType.LEAF,
        status=StepStatus.READY,
        parameters=[
            PlannedParameter(
                name="q",
                display_name="q",
                param_type="string",
                value=StringValue(value="kinase"),
                status=ParamStatus.USER_SET,
                required=True,
            ),
            PlannedParameter(
                name="threshold",
                display_name="threshold",
                param_type="number",
                value=NumberValue(value=0.5),
                status=ParamStatus.DEFAULT,
                required=False,
            ),
        ],
    )
    root = build_step_tree_from_plan(_plan(steps=[step], conns=[]))
    assert root.parameters == {
        "q": StringValue(value="kinase"),
        "threshold": NumberValue(value=0.5),
    }
