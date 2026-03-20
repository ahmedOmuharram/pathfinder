"""Tests for ai.tools.strategy_tools.edit_ops -- delete, undo, rename, update logic."""

from veupath_chatbot.ai.tools.strategy_tools.edit_ops import StrategyEditOps
from veupath_chatbot.domain.strategy.ast import PlanStepNode, StrategyAST
from veupath_chatbot.domain.strategy.ops import CombineOp
from veupath_chatbot.domain.strategy.session import StrategyGraph, StrategySession


def _make_edit_ops(
    *, graph_id: str = "g1", with_steps: bool = True
) -> tuple[StrategyEditOps, StrategyGraph]:
    session = StrategySession("plasmodb")
    graph = session.create_graph("test", graph_id=graph_id)
    graph.record_type = "gene"

    if with_steps:
        step_a = PlanStepNode(search_name="SearchA", parameters={"x": "1"})
        step_b = PlanStepNode(search_name="SearchB", parameters={"y": "2"})
        graph.add_step(step_a)
        graph.add_step(step_b)

    ops = StrategyEditOps.__new__(StrategyEditOps)
    ops.session = session
    return ops, graph


# -- delete_step --


async def test_delete_step_removes_step():
    ops, graph = _make_edit_ops()
    step_ids = list(graph.steps.keys())

    result = await ops.delete_step(step_id=step_ids[0], graph_id="g1")

    assert step_ids[0] not in graph.steps
    assert step_ids[1] in graph.steps
    assert step_ids[0] in result.get("deleted", [])


async def test_delete_step_not_found():
    ops, _graph = _make_edit_ops()

    result = await ops.delete_step(step_id="nonexistent", graph_id="g1")

    assert result["ok"] is False
    assert result["code"] == "STEP_NOT_FOUND"


async def test_delete_step_cascades_to_dependent_steps():
    session = StrategySession("plasmodb")
    graph = session.create_graph("test", graph_id="g1")
    graph.record_type = "gene"

    step_a = PlanStepNode(search_name="A", parameters={})
    step_b = PlanStepNode(search_name="B", parameters={})
    graph.add_step(step_a)
    graph.add_step(step_b)

    combine = PlanStepNode(
        search_name="__combine__",
        parameters={},
        primary_input=step_a,
        secondary_input=step_b,
    )
    combine.operator = CombineOp.UNION
    graph.add_step(combine)

    ops = StrategyEditOps.__new__(StrategyEditOps)
    ops.session = session

    # Deleting step_a should cascade to the combine
    result = await ops.delete_step(step_id=step_a.id, graph_id="g1")

    deleted = result.get("deleted", [])
    assert step_a.id in deleted
    assert combine.id in deleted
    # step_b should remain
    assert step_b.id in graph.steps


async def test_delete_step_refuses_to_delete_all():
    """If deletion would leave zero steps, it should be refused."""
    session = StrategySession("plasmodb")
    graph = session.create_graph("test", graph_id="g1")
    graph.record_type = "gene"
    step = PlanStepNode(search_name="A", parameters={})
    graph.add_step(step)

    ops = StrategyEditOps.__new__(StrategyEditOps)
    ops.session = session

    result = await ops.delete_step(step_id=step.id, graph_id="g1")

    assert result["ok"] is False
    assert result["code"] == "VALIDATION_ERROR"
    assert "clear_strategy" in str(result["message"])


async def test_delete_step_invalidates_old_strategy():
    ops, graph = _make_edit_ops()
    step_ids = list(graph.steps.keys())
    # Set a current strategy rooted at step_ids[0]
    root = graph.steps[step_ids[0]]
    graph.current_strategy = StrategyAST(record_type="gene", root=root, name="Test")

    await ops.delete_step(step_id=step_ids[0], graph_id="g1")

    # After deletion, _with_full_graph rebuilds context plan from remaining steps.
    # The old strategy (rooted at deleted step) should not survive.
    if graph.current_strategy is not None:
        # If rebuilt, it should be rooted at the remaining step, not the deleted one.
        remaining_ids = set(graph.steps.keys())
        all_step_ids = {s.id for s in graph.current_strategy.get_all_steps()}
        assert all_step_ids.issubset(remaining_ids)


# -- undo_last_change --


async def test_undo_with_no_history():
    ops, _graph = _make_edit_ops()

    result = await ops.undo_last_change(graph_id="g1")

    assert result["ok"] is False
    assert "Nothing to undo" in str(result["message"])


async def test_undo_with_history():
    ops, graph = _make_edit_ops()
    step_ids = list(graph.steps.keys())

    # Build a strategy and save two history entries
    root = graph.steps[step_ids[0]]
    strategy = StrategyAST(record_type="gene", root=root, name="V1")
    graph.current_strategy = strategy
    graph.save_history("Initial")

    # Simulate a change
    strategy2 = StrategyAST(record_type="gene", root=root, name="V2")
    graph.current_strategy = strategy2
    graph.save_history("Changed")

    result = await ops.undo_last_change(graph_id="g1")

    assert result["ok"] is True


# -- rename_step --


async def test_rename_step_updates_display_name():
    ops, graph = _make_edit_ops()
    step_ids = list(graph.steps.keys())

    result = await ops.rename_step(
        step_id=step_ids[0], new_name="Renamed Step", graph_id="g1"
    )

    assert result["ok"] is True
    assert graph.steps[step_ids[0]].display_name == "Renamed Step"


async def test_rename_step_not_found():
    ops, _graph = _make_edit_ops()

    result = await ops.rename_step(step_id="nonexistent", new_name="X", graph_id="g1")

    assert result["ok"] is False
    assert result["code"] == "STEP_NOT_FOUND"


# -- update_step --


async def test_update_step_changes_search_name():
    ops, graph = _make_edit_ops()
    step_ids = list(graph.steps.keys())

    result = await ops.update_step(
        step_id=step_ids[0], search_name="NewSearch", graph_id="g1"
    )

    assert result["ok"] is True
    assert graph.steps[step_ids[0]].search_name == "NewSearch"


async def test_update_step_changes_display_name():
    ops, graph = _make_edit_ops()
    step_ids = list(graph.steps.keys())

    result = await ops.update_step(
        step_id=step_ids[0], display_name="Nice Name", graph_id="g1"
    )

    assert result["ok"] is True
    assert graph.steps[step_ids[0]].display_name == "Nice Name"


async def test_update_step_operator_on_leaf_step_rejected():
    """Can't set operator on a leaf step (no secondary input)."""
    ops, graph = _make_edit_ops()
    step_ids = list(graph.steps.keys())

    result = await ops.update_step(step_id=step_ids[0], operator="UNION", graph_id="g1")

    assert result["ok"] is False
    assert "binary steps" in str(result["message"])


async def test_update_step_not_found():
    ops, _graph = _make_edit_ops()

    result = await ops.update_step(step_id="missing", graph_id="g1")

    assert result["ok"] is False
    assert result["code"] == "STEP_NOT_FOUND"
