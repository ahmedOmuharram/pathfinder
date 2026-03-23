"""Tests for ai.tools.strategy_tools.edit_ops -- delete, undo, rename, update logic."""

from veupath_chatbot.ai.tools.strategy_tools.edit_ops import StrategyEditOps
from veupath_chatbot.domain.strategy.ast import PlanStepNode
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
        operator=CombineOp.UNION,
    )
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


async def test_delete_step_removes_from_graph():
    """After deleting a step, it should no longer appear in graph.steps."""
    ops, graph = _make_edit_ops()
    step_ids = list(graph.steps.keys())
    target_id = step_ids[0]
    remaining_id = step_ids[1]

    await ops.delete_step(step_id=target_id, graph_id="g1")

    # The deleted step is gone from graph.steps
    assert target_id not in graph.steps
    # The remaining step is still present
    assert remaining_id in graph.steps
    # Roots are updated: only the remaining step is a root
    assert remaining_id in graph.roots
    assert target_id not in graph.roots


# -- undo_last_change --


async def test_undo_with_no_history():
    ops, _graph = _make_edit_ops()

    result = await ops.undo_last_change(graph_id="g1")

    assert result["ok"] is False
    assert "Nothing to undo" in str(result["message"])


async def test_undo_with_history():
    # Use a single-step graph (1 root) so save_history/to_plan works.
    ops, graph = _make_edit_ops(with_steps=False)
    step = PlanStepNode(search_name="SearchA", parameters={"x": "1"})
    graph.add_step(step)

    graph.save_history("Initial")

    # Simulate a change: update step params.
    step.parameters = {"x": "2"}
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
