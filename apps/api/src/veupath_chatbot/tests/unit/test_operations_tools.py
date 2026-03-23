"""Tests for the composed StrategyTools class (operations.py) and cross-cutting edge cases.

Probes edge cases across the mixin composition: empty graphs, invalid IDs,
state consistency after mutations, and error response format consistency.
"""

from veupath_chatbot.ai.tools.conversation_tools import ConversationTools
from veupath_chatbot.ai.tools.strategy_tools.attachment_ops import (
    StrategyAttachmentOps,
)
from veupath_chatbot.ai.tools.strategy_tools.edit_ops import StrategyEditOps
from veupath_chatbot.ai.tools.strategy_tools.graph_ops import StrategyGraphOps
from veupath_chatbot.domain.strategy.ast import PlanStepNode
from veupath_chatbot.domain.strategy.ops import CombineOp
from veupath_chatbot.domain.strategy.session import StrategyGraph, StrategySession


def _make_graph_ops(
    *, with_steps: bool = True
) -> tuple[StrategyGraphOps, StrategyGraph]:
    session = StrategySession("plasmodb")
    graph = session.create_graph("test", graph_id="g1")
    graph.record_type = "gene"
    if with_steps:
        step_a = PlanStepNode(search_name="SearchA", parameters={"x": "1"})
        step_b = PlanStepNode(search_name="SearchB", parameters={"y": "2"})
        graph.add_step(step_a)
        graph.add_step(step_b)
    ops = StrategyGraphOps.__new__(StrategyGraphOps)
    ops.session = session
    return ops, graph


def _make_edit_ops(*, with_steps: bool = True) -> tuple[StrategyEditOps, StrategyGraph]:
    session = StrategySession("plasmodb")
    graph = session.create_graph("test", graph_id="g1")
    graph.record_type = "gene"
    if with_steps:
        step_a = PlanStepNode(search_name="SearchA", parameters={"x": "1"})
        step_b = PlanStepNode(search_name="SearchB", parameters={"y": "2"})
        graph.add_step(step_a)
        graph.add_step(step_b)
    ops = StrategyEditOps.__new__(StrategyEditOps)
    ops.session = session
    return ops, graph


# ---------------------------------------------------------------------------
# Error response format consistency
# ---------------------------------------------------------------------------


class TestErrorResponseFormat:
    """All tool error responses must have ok=False and code as a string."""

    async def test_graph_not_found_has_ok_false(self):
        ops, _ = _make_graph_ops(with_steps=False)
        await ops.list_current_steps(graph_id="nonexistent")
        # _get_graph falls back to active graph, so this should succeed.
        # But if session has no graph at all:
        session = StrategySession("plasmodb")
        ops2 = StrategyGraphOps.__new__(StrategyGraphOps)
        ops2.session = session
        result2 = await ops2.list_current_steps(graph_id="missing")
        assert result2["ok"] is False
        assert "code" in result2
        assert isinstance(result2["code"], str)

    async def test_delete_step_not_found_has_consistent_format(self):
        ops, _ = _make_edit_ops()
        result = await ops.delete_step(step_id="nonexistent", graph_id="g1")
        assert result["ok"] is False
        assert result["code"] == "STEP_NOT_FOUND"
        assert "message" in result

    async def test_rename_step_not_found_has_consistent_format(self):
        ops, _ = _make_edit_ops()
        result = await ops.rename_step(
            step_id="nonexistent", new_name="X", graph_id="g1"
        )
        assert result["ok"] is False
        assert result["code"] == "STEP_NOT_FOUND"

    async def test_update_step_not_found_has_consistent_format(self):
        ops, _ = _make_edit_ops()
        result = await ops.update_step(step_id="nonexistent", graph_id="g1")
        assert result["ok"] is False
        assert result["code"] == "STEP_NOT_FOUND"


# ---------------------------------------------------------------------------
# Graph state consistency after mutations
# ---------------------------------------------------------------------------


class TestGraphStateConsistency:
    async def test_delete_step_recomputes_roots(self):
        """After deleting a step, roots should be recomputed correctly."""
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
        assert graph.roots == {combine.id}

        ops = StrategyEditOps.__new__(StrategyEditOps)
        ops.session = session

        # Delete the combine step itself, leaving A and B as roots
        await ops.delete_step(step_id=combine.id, graph_id="g1")
        assert step_a.id in graph.roots
        assert step_b.id in graph.roots

    async def test_delete_last_remaining_step_refused(self):
        """Cannot delete the last step -- use clear_strategy instead."""
        session = StrategySession("plasmodb")
        graph = session.create_graph("test", graph_id="g1")
        step = PlanStepNode(search_name="Only", parameters={})
        graph.add_step(step)

        ops = StrategyEditOps.__new__(StrategyEditOps)
        ops.session = session

        result = await ops.delete_step(step_id=step.id, graph_id="g1")
        assert result["ok"] is False
        assert "clear_strategy" in str(result["message"])
        # Step should still exist
        assert step.id in graph.steps

    async def test_validate_graph_after_delete_shows_updated_roots(self):
        """validate_graph_structure should reflect the new state after delete."""
        session = StrategySession("plasmodb")
        graph = session.create_graph("test", graph_id="g1")
        graph.record_type = "gene"

        step_a = PlanStepNode(search_name="A", parameters={})
        step_b = PlanStepNode(search_name="B", parameters={})
        step_c = PlanStepNode(search_name="C", parameters={})
        graph.add_step(step_a)
        graph.add_step(step_b)
        graph.add_step(step_c)

        # Combine A and B
        combine_ab = PlanStepNode(
            search_name="__combine__",
            parameters={},
            primary_input=step_a,
            secondary_input=step_b,
            operator=CombineOp.UNION,
        )
        graph.add_step(combine_ab)

        # Now combine (A+B) and C
        combine_all = PlanStepNode(
            search_name="__combine__",
            parameters={},
            primary_input=combine_ab,
            secondary_input=step_c,
            operator=CombineOp.INTERSECT,
        )
        graph.add_step(combine_all)

        ops_graph = StrategyGraphOps.__new__(StrategyGraphOps)
        ops_graph.session = session
        ops_edit = StrategyEditOps.__new__(StrategyEditOps)
        ops_edit.session = session

        # Before delete: single root
        result = await ops_graph.validate_graph_structure(graph_id="g1")
        assert result["ok"] is True
        assert result["rootCount"] == 1

        # Delete step C -- cascades to combine_all, leaving combine_ab as root
        await ops_edit.delete_step(step_id=step_c.id, graph_id="g1")

        result = await ops_graph.validate_graph_structure(graph_id="g1")
        assert result["rootCount"] == 1
        assert combine_ab.id in result["rootStepIds"]


# ---------------------------------------------------------------------------
# Empty graph edge cases
# ---------------------------------------------------------------------------


class TestEmptyGraphEdgeCases:
    async def test_list_steps_on_empty_graph(self):
        ops, _graph = _make_graph_ops(with_steps=False)
        result = await ops.list_current_steps(graph_id="g1")
        assert result["stepCount"] == 0
        assert result["steps"] == []

    async def test_validate_empty_graph(self):
        ops, _ = _make_graph_ops(with_steps=False)
        result = await ops.validate_graph_structure(graph_id="g1")
        assert result["ok"] is False
        assert any(e["code"] == "EMPTY_GRAPH" for e in result["errors"])

    async def test_ensure_single_output_on_empty_graph(self):
        ops, _ = _make_graph_ops(with_steps=False)
        result = await ops.ensure_single_output(graph_id="g1")
        # Should propagate the validation error
        assert result["ok"] is False


# ---------------------------------------------------------------------------
# Undo edge cases
# ---------------------------------------------------------------------------


class TestUndoEdgeCases:
    async def test_undo_with_single_history_entry_fails(self):
        """undo requires at least 2 history entries to go back."""
        ops, graph = _make_edit_ops()
        graph.save_history("Only entry")

        result = await ops.undo_last_change(graph_id="g1")
        # With only 1 history entry, undo should fail
        assert result["ok"] is False

    async def test_undo_restores_steps(self):
        """After undo, the graph steps should match the previous state."""
        session = StrategySession("plasmodb")
        graph = session.create_graph("test", graph_id="g1")
        graph.record_type = "gene"

        step_a = PlanStepNode(search_name="A", parameters={}, id="sa")
        graph.add_step(step_a)
        graph.save_history("V1 - one step")

        # Update the step's parameters (graph stays at 1 root).
        step_a.parameters = {"updated": "true"}
        graph.save_history("V2 - updated params")

        ops = StrategyEditOps.__new__(StrategyEditOps)
        ops.session = session

        result = await ops.undo_last_change(graph_id="g1")
        assert result["ok"] is True
        # After undo, step_a should have original empty params.
        restored_step = graph.steps.get("sa")
        assert restored_step is not None
        assert restored_step.parameters == {}


# ---------------------------------------------------------------------------
# BUG: update_step does not validate transform step parameters
# ---------------------------------------------------------------------------


class TestUpdateStepTransformValidation:
    """update_step validates parameters for both leaf and transform steps
    (any step where secondary_input is None).  Only binary combine steps
    skip parameter validation.
    """

    async def test_update_step_validates_transform_params(self):
        """Transform step update with invalid parameters triggers validation."""
        session = StrategySession("plasmodb")
        graph = session.create_graph("test", graph_id="g1")
        graph.record_type = "gene"

        leaf = PlanStepNode(search_name="SearchA", parameters={"x": "1"})
        graph.add_step(leaf)

        transform = PlanStepNode(
            search_name="TransformSearch",
            parameters={"threshold": "5"},
            primary_input=leaf,
        )
        graph.add_step(transform)

        ops = StrategyEditOps.__new__(StrategyEditOps)
        ops.session = session

        # update_step on a transform step with invalid parameters triggers validation.
        # The result is an error because the search name is not in the catalog.
        result = await ops.update_step(
            step_id=transform.id,
            parameters={"completely_invalid_param": "garbage_value"},
            graph_id="g1",
        )
        assert result["ok"] is False


# ---------------------------------------------------------------------------
# BUG: rename_step uses _with_plan_payload instead of _with_full_graph
# ---------------------------------------------------------------------------


class TestRenameStepResponseFormat:
    """Verify rename_step includes graphSnapshot like other edit methods."""

    async def test_rename_step_includes_graph_snapshot(self):
        ops, graph = _make_edit_ops()
        step_ids = list(graph.steps.keys())

        result = await ops.rename_step(
            step_id=step_ids[0], new_name="Renamed", graph_id="g1"
        )
        assert result["ok"] is True
        assert "graphSnapshot" in result


# ---------------------------------------------------------------------------
# clear_strategy resets WDK state
# ---------------------------------------------------------------------------


class TestClearStrategyWdkState:
    """clear_strategy resets steps, roots, history,
    AND WDK state (wdk_strategy_id, wdk_step_ids, step_counts).
    """

    async def test_clear_resets_wdk_state(self):
        session = StrategySession("plasmodb")
        graph = session.create_graph("test", graph_id="g1")
        step = PlanStepNode(search_name="A", parameters={})
        graph.add_step(step)

        # Simulate a built strategy
        graph.wdk_strategy_id = 42
        graph.wdk_step_ids = {step.id: 100}
        graph.step_counts = {step.id: 150}

        tools = ConversationTools(session)
        result = await tools.clear_strategy(graph_id="g1", confirm=True)
        assert result["ok"] is True
        assert len(graph.steps) == 0

        # Clearing a strategy resets WDK state.
        assert graph.wdk_strategy_id is None
        assert graph.wdk_step_ids == {}
        assert graph.step_counts == {}


# ---------------------------------------------------------------------------
# _get_graph fallback behavior
# ---------------------------------------------------------------------------


class TestGetGraphFallback:
    """_get_graph falls back to session.get_graph(None) when the ID doesn't match.
    This is intentional but can mask bugs where the AI passes a wrong graph_id.
    """

    async def test_wrong_graph_id_falls_back_to_active(self):
        ops, _graph = _make_graph_ops()
        # Passing a wrong graph ID still returns data from the active graph
        result = await ops.list_current_steps(graph_id="wrong_id")
        assert result["graphId"] == "g1"
        assert result["stepCount"] == 2

    async def test_no_active_graph_returns_error(self):
        session = StrategySession("plasmodb")
        ops = StrategyGraphOps.__new__(StrategyGraphOps)
        ops.session = session
        result = await ops.list_current_steps(graph_id="any")
        assert result["ok"] is False
        assert result["code"] == "NOT_FOUND"


# ---------------------------------------------------------------------------
# Step ID edge cases
# ---------------------------------------------------------------------------


class TestStepIdEdgeCases:
    async def test_empty_string_step_id_for_delete(self):
        ops, _ = _make_edit_ops()
        result = await ops.delete_step(step_id="", graph_id="g1")
        assert result["ok"] is False
        assert result["code"] == "STEP_NOT_FOUND"

    async def test_empty_string_step_id_for_rename(self):
        ops, _ = _make_edit_ops()
        result = await ops.rename_step(step_id="", new_name="X", graph_id="g1")
        assert result["ok"] is False
        assert result["code"] == "STEP_NOT_FOUND"

    async def test_empty_string_step_id_for_update(self):
        ops, _ = _make_edit_ops()
        result = await ops.update_step(step_id="", graph_id="g1")
        assert result["ok"] is False
        assert result["code"] == "STEP_NOT_FOUND"


# ---------------------------------------------------------------------------
# update_step with no changes (noop)
# ---------------------------------------------------------------------------


class TestUpdateStepNoop:
    async def test_update_with_no_changes_succeeds(self):
        """Calling update_step with no optional args should be a noop."""
        ops, graph = _make_edit_ops()
        step_ids = list(graph.steps.keys())
        original_name = graph.steps[step_ids[0]].search_name

        result = await ops.update_step(step_id=step_ids[0], graph_id="g1")
        assert result["ok"] is True
        assert graph.steps[step_ids[0]].search_name == original_name

    async def test_update_with_empty_display_name_is_noop(self):
        """display_name='' should be falsy and thus NOT update."""
        ops, graph = _make_edit_ops()
        step_ids = list(graph.steps.keys())
        original_name = graph.steps[step_ids[0]].display_name

        result = await ops.update_step(
            step_id=step_ids[0], display_name="", graph_id="g1"
        )
        assert result["ok"] is True
        # Empty string is falsy, so display_name should NOT be updated
        assert graph.steps[step_ids[0]].display_name == original_name


# ---------------------------------------------------------------------------
# Multiple filters with same name -- replacement behavior
# ---------------------------------------------------------------------------


class TestFilterReplacement:
    async def test_filter_with_same_name_replaces(self):
        """Adding a filter with the same name should replace the old one."""
        session = StrategySession("plasmodb")
        graph = session.create_graph("test", graph_id="g1")
        step = PlanStepNode(search_name="Search", parameters={})
        graph.add_step(step)

        ops = StrategyAttachmentOps.__new__(StrategyAttachmentOps)
        ops.session = session

        await ops.add_step_filter(
            step_id=step.id, filter_name="org", value="old_org", graph_id="g1"
        )
        await ops.add_step_filter(
            step_id=step.id, filter_name="other", value="keep", graph_id="g1"
        )
        await ops.add_step_filter(
            step_id=step.id, filter_name="org", value="new_org", graph_id="g1"
        )

        # Should have 2 filters, not 3
        assert len(step.filters) == 2
        org_filters = [f for f in step.filters if f.name == "org"]
        assert len(org_filters) == 1
        assert org_filters[0].value == "new_org"

    async def test_analyses_accumulate_not_replace(self):
        """Adding analyses with the same type should accumulate, not replace."""
        session = StrategySession("plasmodb")
        graph = session.create_graph("test", graph_id="g1")
        step = PlanStepNode(search_name="Search", parameters={})
        graph.add_step(step)

        ops = StrategyAttachmentOps.__new__(StrategyAttachmentOps)
        ops.session = session

        await ops.add_step_analysis(
            step_id=step.id, analysis_type="enrichment", graph_id="g1"
        )
        await ops.add_step_analysis(
            step_id=step.id, analysis_type="enrichment", graph_id="g1"
        )

        # Analyses accumulate (unlike filters which replace by name)
        assert len(step.analyses) == 2


# ---------------------------------------------------------------------------
# Operator validation on update_step for non-binary steps
# ---------------------------------------------------------------------------


class TestOperatorOnNonBinaryStep:
    async def test_setting_operator_on_leaf_step_rejected(self):
        ops, graph = _make_edit_ops()
        step_ids = list(graph.steps.keys())

        result = await ops.update_step(
            step_id=step_ids[0], operator="UNION", graph_id="g1"
        )
        assert result["ok"] is False
        assert "binary steps" in str(result["message"])

    async def test_setting_operator_on_binary_step_accepted(self):
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

        result = await ops.update_step(
            step_id=combine.id, operator="INTERSECT", graph_id="g1"
        )
        assert result["ok"] is True
        assert combine.operator == CombineOp.INTERSECT
