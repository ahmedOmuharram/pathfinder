"""Tests for standalone strategy build tools (leaf, combine, transform)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai.messages import ToolReturn

from pathfinder.ai.agents.state import AgentToolState, SearchOverview
from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.tools.standalone._validation_helpers import StepOkResponse
from pathfinder.ai.tools.standalone.strategy_build import (
    combine_steps,
    create_leaf_step,
    transform_step,
)
from pathfinder.domain.strategy.ast import PlanStepNode
from pathfinder.domain.strategy.ops import CombineOp
from pathfinder.domain.strategy.session import StrategySession
from pathfinder.platform.tool_errors import ToolErrorPayload
from pathfinder.services.strategies.step_creation import StepCreationResult


def _make_session(site_id: str = "plasmodb") -> StrategySession:
    session = StrategySession(site_id=site_id)
    graph = session.create_graph("Test Strategy")
    graph.record_type = "transcript"
    return session


def _make_deps(
    session: StrategySession,
    agent_state: AgentToolState | None = None,
) -> AgentDeps:
    return AgentDeps(
        site_id=session.site_id,
        strategy_session=session,
        agent_state=agent_state or AgentToolState(),
    )


def _make_ctx(deps: AgentDeps) -> MagicMock:
    ctx = MagicMock()
    ctx.deps = deps
    return ctx


def _register_search(state: AgentToolState, search_name: str) -> None:
    state.register_search(
        search_name,
        SearchOverview(
            search_name=search_name,
            display_name=f"{search_name} Display",
            record_type="transcript",
            description=f"Test search {search_name}",
            parameter_names=["organism", "min_expr"],
            required_params=["organism"],
        ),
    )


@pytest.mark.asyncio
async def test_create_leaf_step_requires_discovery() -> None:
    session = _make_session()
    state = AgentToolState()
    deps = _make_deps(session, state)
    ctx = _make_ctx(deps)

    result = await create_leaf_step(
        ctx,
        search_name="GenesByTaxon",
        parameters={"organism": "Plasmodium falciparum 3D7"},
    )

    assert isinstance(result, ToolErrorPayload)
    assert result.code == "DISCOVERY_REQUIRED"
    assert "get_search_overview" in result.message
    assert result.details is not None
    assert result.details["required_action"] == "get_search_overview(search_name='GenesByTaxon')"


@pytest.mark.asyncio
@patch("pathfinder.ai.tools.standalone.strategy_build.create_step", new_callable=AsyncMock)
async def test_create_leaf_step_after_discovery(
    mock_create_step: AsyncMock,
) -> None:
    session = _make_session()
    state = AgentToolState()
    _register_search(state, "GenesByTaxon")
    deps = _make_deps(session, state)
    ctx = _make_ctx(deps)

    graph = session.get_graph(None)
    assert graph is not None

    created_step = PlanStepNode(
        search_name="GenesByTaxon",
        display_name="Genes by Taxon",
        parameters={"organism": "Plasmodium falciparum 3D7"},
    )
    graph.add_step(created_step)

    mock_create_step.return_value = StepCreationResult(
        step=created_step,
        step_id=created_step.id,
        error=None,
    )

    result = await create_leaf_step(
        ctx,
        search_name="GenesByTaxon",
        parameters={"organism": "Plasmodium falciparum 3D7"},
        display_name="Genes by Taxon",
    )

    assert isinstance(result, ToolReturn)
    payload = result.return_value
    assert isinstance(payload, StepOkResponse)
    assert payload.ok is True
    assert payload.step.search_name == "GenesByTaxon"
    assert payload.step.display_name == "Genes by Taxon"
    assert payload.graph_id == graph.id


@pytest.mark.asyncio
@patch("pathfinder.ai.tools.standalone.strategy_build.create_step", new_callable=AsyncMock)
async def test_combine_steps_creates_union(
    mock_create_step: AsyncMock,
) -> None:
    session = _make_session()
    state = AgentToolState()
    deps = _make_deps(session, state)
    ctx = _make_ctx(deps)

    graph = session.get_graph(None)
    assert graph is not None

    step_a = PlanStepNode(search_name="GenesByTaxon", display_name="Step A")
    step_b = PlanStepNode(search_name="GenesByLocation", display_name="Step B")
    graph.add_step(step_a)
    graph.add_step(step_b)

    combined = PlanStepNode(
        search_name="__combine__",
        display_name="Union of A and B",
        primary_input=step_a,
        secondary_input=step_b,
        operator=CombineOp.UNION,
    )
    graph.add_step(combined)

    mock_create_step.return_value = StepCreationResult(
        step=combined,
        step_id=combined.id,
        error=None,
    )

    result = await combine_steps(
        ctx,
        step_a_id=step_a.id,
        step_b_id=step_b.id,
        operator="UNION",
    )

    assert isinstance(result, ToolReturn)
    payload = result.return_value
    assert isinstance(payload, StepOkResponse)
    assert payload.ok is True
    assert payload.step.id == combined.id


@pytest.mark.asyncio
async def test_combine_steps_rejects_missing_step() -> None:
    session = _make_session()
    deps = _make_deps(session)
    ctx = _make_ctx(deps)

    graph = session.get_graph(None)
    assert graph is not None

    step_a = PlanStepNode(search_name="GenesByTaxon", display_name="Step A")
    graph.add_step(step_a)

    result = await combine_steps(
        ctx,
        step_a_id=step_a.id,
        step_b_id="nonexistent-id",
        operator="INTERSECT",
    )

    assert isinstance(result, ToolErrorPayload)
    assert result.code == "STEP_NOT_FOUND"
    assert "nonexistent-id" in result.message


@pytest.mark.asyncio
async def test_combine_steps_rejects_invalid_operator() -> None:
    session = _make_session()
    deps = _make_deps(session)
    ctx = _make_ctx(deps)

    graph = session.get_graph(None)
    assert graph is not None

    step_a = PlanStepNode(search_name="GenesByTaxon", display_name="Step A")
    step_b = PlanStepNode(search_name="GenesByLocation", display_name="Step B")
    graph.add_step(step_a)
    graph.add_step(step_b)

    result = await combine_steps(
        ctx,
        step_a_id=step_a.id,
        step_b_id=step_b.id,
        operator="INVALID_OP",
    )

    assert isinstance(result, ToolErrorPayload)
    assert result.code == "VALIDATION_ERROR"
    assert "INTERSECT" in result.message


@pytest.mark.asyncio
async def test_transform_step_requires_discovery_with_params() -> None:
    session = _make_session()
    state = AgentToolState()
    deps = _make_deps(session, state)
    ctx = _make_ctx(deps)

    graph = session.get_graph(None)
    assert graph is not None

    step = PlanStepNode(search_name="GenesByTaxon", display_name="Source")
    graph.add_step(step)

    result = await transform_step(
        ctx,
        input_step_id=step.id,
        transform_name="GenesByOrthologPattern",
        parameters={"profile_pattern": "%pfal3D7:Y%"},
    )

    assert isinstance(result, ToolErrorPayload)
    assert result.code == "DISCOVERY_REQUIRED"


@pytest.mark.asyncio
async def test_transform_step_missing_input_step() -> None:
    session = _make_session()
    state = AgentToolState()
    _register_search(state, "GenesByOrthologPattern")
    deps = _make_deps(session, state)
    ctx = _make_ctx(deps)

    result = await transform_step(
        ctx,
        input_step_id="nonexistent",
        transform_name="GenesByOrthologPattern",
        parameters={"profile_pattern": "%pfal3D7:Y%"},
    )

    assert isinstance(result, ToolErrorPayload)
    assert result.code == "STEP_NOT_FOUND"
