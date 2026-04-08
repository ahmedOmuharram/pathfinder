"""Integration tests for standalone plan tools (create, get, update, submit).

Uses real AgentToolState and AgentDeps — only RunContext is a mock wrapper.
"""

from unittest.mock import MagicMock

import pytest

from pathfinder.ai.agents.state import AgentToolState, SearchOverview
from pathfinder.ai.orchestration.deps import AgentDeps
from pathfinder.ai.tools.standalone._plan_models import (
    PlanCreatedResponse,
    PlannedConnectionInput,
    PlannedStepInput,
    StepPatch,
)
from pathfinder.ai.tools.standalone.plan import (
    create_plan,
    get_plan,
    submit_plan,
    update_plan,
)
from pathfinder.domain.strategy.plan import (
    ParamStatus,
    PlanStatus,
    StepType,
    StrategyPlan,
)
from pathfinder.domain.strategy.session import StrategySession
from pathfinder.platform.tool_errors import ToolErrorPayload

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_deps(site_id: str = "plasmodb") -> AgentDeps:
    session = StrategySession(site_id=site_id)
    return AgentDeps(
        site_id=site_id,
        strategy_session=session,
        agent_state=AgentToolState(),
    )


def _make_ctx(deps: AgentDeps) -> MagicMock:
    ctx = MagicMock()
    ctx.deps = deps
    return ctx


def _leaf_step(
    step_id: str = "step_a",
    search_name: str = "GenesByTaxon",
) -> PlannedStepInput:
    return PlannedStepInput(
        id=step_id,
        search_name=search_name,
        display_name=f"Step: {search_name}",
        record_type="transcript",
        step_type=StepType.LEAF,
        parameters={"organism": '["Plasmodium falciparum 3D7"]'},
    )


def _combine_step(step_id: str = "step_combine") -> PlannedStepInput:
    return PlannedStepInput(
        id=step_id,
        search_name="__combine__",
        display_name="Combine",
        record_type="transcript",
        step_type=StepType.COMBINE,
        operator="INTERSECT",
    )


def _connection(from_step: str, to_step: str) -> PlannedConnectionInput:
    return PlannedConnectionInput(
        from_step=from_step,
        to_step=to_step,
        input_type="primary",
    )


def _register_search(state: AgentToolState, search_name: str) -> None:
    state.register_search(
        search_name,
        SearchOverview(
            search_name=search_name,
            display_name=f"{search_name} Display",
            record_type="transcript",
            description=f"Test search {search_name}",
            parameter_names=["organism"],
            required_params=["organism"],
        ),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_plan_stores_plan_in_agent_state() -> None:
    """create_plan should set deps.agent_state.active_plan with correct counts."""
    deps = _make_deps()
    ctx = _make_ctx(deps)

    step_a = _leaf_step("step_a", "GenesByTaxon")
    step_b = _leaf_step("step_b", "GenesByLocation")
    combine = _combine_step("step_c")
    connections = [
        _connection("step_a", "step_c"),
        _connection("step_b", "step_c"),
    ]

    result = await create_plan(
        ctx,
        title="Test Plan",
        description="Find genes by location and taxon",
        rationale="Intersect two gene sets",
        steps=[step_a, step_b, combine],
        connections=connections,
    )

    assert isinstance(result, PlanCreatedResponse)
    assert result.title == "Test Plan"
    assert result.step_count == 3

    plan = deps.agent_state.active_plan
    assert plan is not None
    assert plan.title == "Test Plan"
    assert len(plan.steps) == 3
    assert len(plan.connections) == 2
    assert plan.status == PlanStatus.DRAFT


@pytest.mark.asyncio
async def test_submit_plan_validates_topology() -> None:
    """submit_plan should reject a plan with a disconnected step reference."""
    deps = _make_deps()
    ctx = _make_ctx(deps)

    step_a = _leaf_step("step_a", "GenesByTaxon")
    # Connection references a non-existent step "step_ghost"
    bad_connection = _connection("step_a", "step_ghost")

    result = await create_plan(
        ctx,
        title="Bad Topology",
        description="This plan has a topology error",
        rationale="Testing",
        steps=[step_a],
        connections=[bad_connection],
    )

    # create_plan itself catches topology errors
    assert isinstance(result, ToolErrorPayload)
    assert result.code == "TOPOLOGY_ERROR"
    assert "step_ghost" in result.message


@pytest.mark.asyncio
async def test_submit_plan_validates_parameters() -> None:
    """submit_plan should reject when a leaf step has unset required params."""
    deps = _make_deps()
    ctx = _make_ctx(deps)

    # Create a step with an explicitly NEEDS_DISCOVERY param
    step_a = PlannedStepInput(
        id="step_a",
        search_name="GenesByTaxon",
        display_name="Genes by Taxon",
        record_type="transcript",
        step_type=StepType.LEAF,
        parameters={},  # No parameters set
    )

    # First create the plan
    create_result = await create_plan(
        ctx,
        title="Missing Params Plan",
        description="This plan has missing parameters",
        rationale="Testing parameter validation",
        steps=[step_a],
        connections=[],
    )
    assert isinstance(create_result, PlanCreatedResponse)

    # Manually mark a required parameter as NEEDS_DISCOVERY to trigger validation
    plan = deps.agent_state.active_plan
    assert plan is not None
    plan.steps[0].parameters["organism"] = plan.steps[0].parameters.get(
        "organism",
        # Add a required param that is not set
        __import__(
            "pathfinder.domain.strategy.plan", fromlist=["PlannedParameter"]
        ).PlannedParameter(
            name="organism",
            display_name="Organism",
            param_type="string",
            value=None,
            status=ParamStatus.NEEDS_DISCOVERY,
            required=True,
        ),
    )

    submit_result = await submit_plan(ctx)

    assert isinstance(submit_result, ToolErrorPayload)
    assert submit_result.code == "PARAMETER_ERROR"
    assert "organism" in submit_result.message


@pytest.mark.asyncio
async def test_update_plan_applies_step_patches() -> None:
    """update_plan with a StepPatch should modify the step's parameter."""
    deps = _make_deps()
    ctx = _make_ctx(deps)

    step_a = _leaf_step("step_a", "GenesByTaxon")
    await create_plan(
        ctx,
        title="Original Plan",
        description="Original description",
        rationale="Original rationale",
        steps=[step_a],
        connections=[],
    )

    plan_before = deps.agent_state.active_plan
    assert plan_before is not None
    assert plan_before.version == 1

    # Apply a patch to change the organism parameter
    patch = StepPatch(
        step_id="step_a",
        parameters={"organism": '["Plasmodium vivax"]'},
    )

    result = await update_plan(ctx, step_updates=[patch])

    assert isinstance(result, StrategyPlan)
    assert result.version == 2

    # Verify the parameter was actually changed
    patched_step = result.steps[0]
    assert patched_step.id == "step_a"
    assert patched_step.parameters["organism"].value == '["Plasmodium vivax"]'
    assert patched_step.parameters["organism"].status == ParamStatus.SET


@pytest.mark.asyncio
async def test_get_plan_returns_active_plan() -> None:
    """get_plan should return the same plan that create_plan stored."""
    deps = _make_deps()
    ctx = _make_ctx(deps)

    step_a = _leaf_step("step_a", "GenesByTaxon")
    create_result = await create_plan(
        ctx,
        title="My Plan",
        description="Test plan",
        rationale="Testing get_plan",
        steps=[step_a],
        connections=[],
    )
    assert isinstance(create_result, PlanCreatedResponse)

    get_result = await get_plan(ctx)

    assert isinstance(get_result, StrategyPlan)
    assert get_result.title == "My Plan"
    assert get_result.id == create_result.plan_id
    assert len(get_result.steps) == 1
    assert get_result.steps[0].search_name == "GenesByTaxon"


@pytest.mark.asyncio
async def test_get_plan_returns_error_when_no_plan() -> None:
    """get_plan should return a ToolErrorPayload when no plan exists."""
    deps = _make_deps()
    ctx = _make_ctx(deps)

    result = await get_plan(ctx)

    assert isinstance(result, ToolErrorPayload)
    assert result.code == "NO_ACTIVE_PLAN"


@pytest.mark.asyncio
async def test_update_plan_returns_error_when_no_plan() -> None:
    """update_plan should return a ToolErrorPayload when no plan exists."""
    deps = _make_deps()
    ctx = _make_ctx(deps)

    result = await update_plan(ctx, title="New Title")

    assert isinstance(result, ToolErrorPayload)
    assert result.code == "NO_ACTIVE_PLAN"


@pytest.mark.asyncio
async def test_create_plan_archives_previous_plan() -> None:
    """Creating a second plan should archive the first."""
    deps = _make_deps()
    ctx = _make_ctx(deps)

    step_a = _leaf_step("step_a", "GenesByTaxon")
    await create_plan(
        ctx,
        title="Plan 1",
        description="First plan",
        rationale="Testing archival",
        steps=[step_a],
        connections=[],
    )

    first_plan = deps.agent_state.active_plan
    assert first_plan is not None
    assert first_plan.title == "Plan 1"
    assert len(deps.agent_state.plan_history) == 0

    step_b = _leaf_step("step_b", "GenesByLocation")
    await create_plan(
        ctx,
        title="Plan 2",
        description="Second plan",
        rationale="Replaced first",
        steps=[step_b],
        connections=[],
    )

    second_plan = deps.agent_state.active_plan
    assert second_plan is not None
    assert second_plan.title == "Plan 2"
    assert len(deps.agent_state.plan_history) == 1
    assert deps.agent_state.plan_history[0].title == "Plan 1"
