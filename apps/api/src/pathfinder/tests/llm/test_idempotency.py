from __future__ import annotations

import contextlib

import pytest
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.messages import ModelResponse, ToolCallPart, ToolReturnPart
from pydantic_ai.usage import UsageLimits

from pathfinder.ai.agents.planning import planning_agent
from pathfinder.ai.agents.state import SearchOverview
from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.graph.state import ProblemFrame
from pathfinder.domain.strategy.plan import (
    ParamStatus,
    PlannedParameter,
    PlannedStep,
    PlanStatus,
    StepStatus,
    StepType,
    StrategyPlan,
)


def _pre_approved_kinase_plan() -> StrategyPlan:
    org_param = PlannedParameter(
        name="organism",
        display_name="organism",
        param_type="multi-pick-vocabulary",
        value=["Plasmodium falciparum 3D7"],
        status=ParamStatus.SET,
        required=True,
    )
    steps = [
        PlannedStep(
            id="kinase",
            search_name="GenesByGoTerm",
            display_name="GO:0016301 kinase",
            step_type=StepType.LEAF,
            status=StepStatus.READY,
            parameters=[org_param],
        ),
    ]
    return StrategyPlan(
        id="plan_preexist01",
        title="Existing Approved Kinase Plan",
        description="Pre-approved plan to verify idempotency",
        rationale="Fixture",
        status=PlanStatus.APPROVED,
        steps=steps,
        connections=[],
    )


@pytest.mark.asyncio
async def test_planner_does_not_recreate_approved_plan(
    deps_planning: AgentDeps,
    kinase_problem_frame: ProblemFrame,
    kinase_discovered_searches: dict[str, SearchOverview],
) -> None:
    del kinase_problem_frame, kinase_discovered_searches
    existing = _pre_approved_kinase_plan()
    deps_planning.agent_state.active_plan = existing

    prompt = (
        "Plan looks good overall. I'd like to also add a step that filters "
        "to genes with at least one transmembrane domain. Use `update_plan` "
        "to add ONE new step then `submit_plan`. Do NOT call `create_plan`."
    )
    result = None
    with contextlib.suppress(UsageLimitExceeded):
        result = await planning_agent.run(
            prompt,
            deps=deps_planning,
            usage_limits=UsageLimits(
                request_limit=120, tool_calls_limit=120,
            ),
        )

    create_plan_calls: list[ToolCallPart] = []
    create_plan_errors = 0
    messages = list(result.new_messages()) if result is not None else []
    for msg in messages:
        if isinstance(msg, ModelResponse):
            create_plan_calls.extend(
                part
                for part in msg.parts
                if isinstance(part, ToolCallPart)
                and part.tool_name == "create_plan"
            )
        else:
            for part in msg.parts:
                if (
                    isinstance(part, ToolReturnPart)
                    and part.tool_name == "create_plan"
                    and "PLAN_ALREADY_EXISTS" in str(part.content)
                ):
                    create_plan_errors += 1

    if create_plan_calls:
        assert create_plan_errors == len(create_plan_calls), (
            f"every create_plan call must receive PLAN_ALREADY_EXISTS; "
            f"got {len(create_plan_calls)} calls and "
            f"{create_plan_errors} errors"
        )

    current = deps_planning.agent_state.active_plan
    assert current is not None
    assert current.id == existing.id, (
        f"active_plan id must be preserved; got {current.id} (was {existing.id})"
    )
    assert current.status.value == "approved", (
        f"plan status must remain APPROVED; got {current.status.value}"
    )
