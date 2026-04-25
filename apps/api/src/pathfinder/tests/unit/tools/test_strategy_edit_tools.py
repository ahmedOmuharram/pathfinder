"""Integration tests for standalone strategy edit tools (delete, update, undo).

Uses real StrategySession, StrategyGraph, and StrategyStepNode objects.
Only RunContext is a mock wrapper around real AgentDeps.
"""

from unittest.mock import MagicMock

import pytest
from pydantic_ai.exceptions import ModelRetry
from pydantic_ai.messages import ToolReturn

from pathfinder.ai.agents.state import AgentToolState
from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.tools.standalone.strategy_edit import (
    delete_step,
    undo_last_change,
    update_step,
)
from pathfinder.domain.strategy.ast import StrategyStepNode
from pathfinder.domain.strategy.ops import CombineOp
from pathfinder.domain.strategy.session import StrategyGraph, StrategySession

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def _add_leaf(
    graph: StrategyGraph,
    step_id: str,
    search_name: str = "GenesByTaxon",
) -> StrategyStepNode:
    step = StrategyStepNode(
        id=step_id,
        search_name=search_name,
        display_name=f"Step: {search_name}",
        parameters={"organism": '["Plasmodium falciparum 3D7"]'},
    )
    graph.add_step(step)
    return step


def _add_combined(
    graph: StrategyGraph,
    step_a: StrategyStepNode,
    step_b: StrategyStepNode,
    operator: CombineOp = CombineOp.INTERSECT,
) -> StrategyStepNode:
    combine = StrategyStepNode(
        search_name="__combine__",
        display_name="Intersect",
        primary_input=step_a,
        secondary_input=step_b,
        operator=operator,
    )
    graph.add_step(combine)
    return combine


# ---------------------------------------------------------------------------
# delete_step tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_step_refuses_last_step() -> None:
    """Deleting the only step should return an error suggesting clear_strategy."""
    session = _make_session()
    graph = session.get_graph(None)
    assert graph is not None

    _add_leaf(graph, "step_1")

    deps = _make_deps(session)
    ctx = _make_ctx(deps)

    with pytest.raises(ModelRetry) as excinfo:
        await delete_step(ctx, step_id="step_1")

    msg = str(excinfo.value)
    assert "VALIDATION_ERROR" in msg
    assert "clear_strategy" in msg


@pytest.mark.asyncio
async def test_delete_step_missing_step_returns_error() -> None:
    """Deleting a step_id not in the graph should return NOT_FOUND-style error."""
    session = _make_session()
    graph = session.get_graph(None)
    assert graph is not None

    _add_leaf(graph, "step_1")
    _add_leaf(graph, "step_2")

    deps = _make_deps(session)
    ctx = _make_ctx(deps)

    with pytest.raises(ModelRetry) as excinfo:
        await delete_step(ctx, step_id="nonexistent_step")

    msg = str(excinfo.value)
    assert "VALIDATION_ERROR" in msg
    assert "nonexistent_step" in msg


@pytest.mark.asyncio
async def test_delete_step_removes_leaf_from_combined() -> None:
    """Deleting a leaf that's part of a combine should collapse the combine."""
    session = _make_session()
    graph = session.get_graph(None)
    assert graph is not None

    step_a = _add_leaf(graph, "step_a", "GenesByTaxon")
    step_b = _add_leaf(graph, "step_b", "GenesByLocation")
    combine = _add_combined(graph, step_a, step_b)

    assert len(graph.steps) == 3

    deps = _make_deps(session)
    ctx = _make_ctx(deps)

    result = await delete_step(ctx, step_id="step_b")

    assert isinstance(result, ToolReturn)
    payload = result.return_value
    assert isinstance(payload, dict)
    deleted = payload.get("deleted")
    assert isinstance(deleted, list)
    # step_b and the combine node should be deleted
    assert "step_b" in deleted
    assert combine.id in deleted
    # step_a should survive
    assert "step_a" in graph.steps


# ---------------------------------------------------------------------------
# update_step tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_step_invalid_operator_returns_error() -> None:
    """Setting an invalid operator on a binary step should return VALIDATION_ERROR."""
    session = _make_session()
    graph = session.get_graph(None)
    assert graph is not None

    step_a = _add_leaf(graph, "step_a", "GenesByTaxon")
    step_b = _add_leaf(graph, "step_b", "GenesByLocation")
    combine = _add_combined(graph, step_a, step_b)

    deps = _make_deps(session)
    ctx = _make_ctx(deps)

    with pytest.raises(ModelRetry) as excinfo:
        await update_step(ctx, step_id=combine.id, operator="INVALID_OPERATOR")

    msg = str(excinfo.value)
    assert "VALIDATION_ERROR" in msg
    assert "INVALID_OPERATOR" in msg


@pytest.mark.asyncio
async def test_update_step_operator_on_leaf_returns_error() -> None:
    """Setting operator on a non-binary (leaf) step should return error."""
    session = _make_session()
    graph = session.get_graph(None)
    assert graph is not None

    _add_leaf(graph, "step_a")

    deps = _make_deps(session)
    ctx = _make_ctx(deps)

    with pytest.raises(ModelRetry) as excinfo:
        await update_step(ctx, step_id="step_a", operator="INTERSECT")

    msg = str(excinfo.value)
    assert "VALIDATION_ERROR" in msg
    assert "binary" in msg.lower()


# ---------------------------------------------------------------------------
# undo_last_change tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_undo_with_no_history_returns_error() -> None:
    """Undo with insufficient history should return a validation error."""
    session = _make_session()
    graph = session.get_graph(None)
    assert graph is not None

    _add_leaf(graph, "step_a")

    deps = _make_deps(session)
    ctx = _make_ctx(deps)

    with pytest.raises(ModelRetry) as excinfo:
        await undo_last_change(ctx)

    assert "VALIDATION_ERROR" in str(excinfo.value)


@pytest.mark.asyncio
async def test_undo_restores_previous_state() -> None:
    """After saving history and making a change, undo should restore prior state."""
    session = _make_session()
    graph = session.get_graph(None)
    assert graph is not None

    # Build initial state and save history twice (undo requires >= 2 entries)
    _add_leaf(graph, "step_a", "GenesByTaxon")
    graph.save_history("initial state")
    graph.save_history("still initial")

    assert len(graph.history) == 2

    # Now modify the graph by adding a second step
    _add_leaf(graph, "step_b", "GenesByLocation")
    graph.save_history("added step_b")

    assert len(graph.steps) == 2
    assert "step_b" in graph.steps

    deps = _make_deps(session)
    ctx = _make_ctx(deps)

    result = await undo_last_change(ctx)

    assert isinstance(result, ToolReturn)
    payload = result.return_value
    assert isinstance(payload, dict)
    # After undo, the graph should be restored to the "still initial" snapshot
    # which had only step_a
    assert payload.get("ok") is True
    assert payload.get("message") == "Undone to previous state"
