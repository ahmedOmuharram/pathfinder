"""Tests for always-connected graph operations on StrategyGraph.

Covers find_parent, insert_step_with_combine, and delete_step_connected.
Every test asserts the single-root invariant: len(graph.roots) <= 1.
"""

import pytest

from veupath_chatbot.domain.strategy.ast import COMBINE_SEARCH_NAME, PlanStepNode
from veupath_chatbot.domain.strategy.ops import CombineOp
from veupath_chatbot.domain.strategy.session import StrategyGraph


def _make_graph() -> StrategyGraph:
    return StrategyGraph("test-graph", "Test", "plasmodb.org")


def _leaf(name: str = "GenesByTaxon", step_id: str | None = None) -> PlanStepNode:
    return PlanStepNode(
        search_name=name,
        parameters={"organism": "Plasmodium falciparum 3D7"},
        id=step_id or f"step_{name.lower()}",
    )


def _assert_invariant(graph: StrategyGraph) -> None:
    __tracebackhide__ = True
    assert len(graph.roots) <= 1, (
        f"Single-root invariant violated: {len(graph.roots)} roots ({graph.roots})"
    )


# ---------------------------------------------------------------------------
# find_parent
# ---------------------------------------------------------------------------


class TestFindParent:
    def test_root_returns_none(self) -> None:
        graph = _make_graph()
        step_a = _leaf("A", "step_a")
        graph.add_step(step_a)
        assert graph.find_parent("step_a") is None

    def test_primary_child(self) -> None:
        graph = _make_graph()
        step_a = _leaf("A", "step_a")
        combine = PlanStepNode(
            search_name=COMBINE_SEARCH_NAME,
            primary_input=step_a,
            secondary_input=_leaf("B", "step_b"),
            operator=CombineOp.INTERSECT,
            id="step_combine",
        )
        graph.steps = {s.id: s for s in [step_a, combine.secondary_input, combine]}
        graph.recompute_roots()

        result = graph.find_parent("step_a")
        assert result is not None
        parent, slot = result
        assert parent.id == "step_combine"
        assert slot == "primary"

    def test_secondary_child(self) -> None:
        graph = _make_graph()
        step_a = _leaf("A", "step_a")
        step_b = _leaf("B", "step_b")
        combine = PlanStepNode(
            search_name=COMBINE_SEARCH_NAME,
            primary_input=step_a,
            secondary_input=step_b,
            operator=CombineOp.INTERSECT,
            id="step_combine",
        )
        graph.steps = {s.id: s for s in [step_a, step_b, combine]}
        graph.recompute_roots()

        result = graph.find_parent("step_b")
        assert result is not None
        parent, slot = result
        assert parent.id == "step_combine"
        assert slot == "secondary"

    def test_nonexistent_step(self) -> None:
        graph = _make_graph()
        assert graph.find_parent("does_not_exist") is None

    def test_nested_child(self) -> None:
        """Find parent in a deeper tree: A -> combine(A, B) -> combine2(combine, C)."""
        graph = _make_graph()
        step_a = _leaf("A", "step_a")
        step_b = _leaf("B", "step_b")
        step_c = _leaf("C", "step_c")
        combine1 = PlanStepNode(
            search_name=COMBINE_SEARCH_NAME,
            primary_input=step_a,
            secondary_input=step_b,
            operator=CombineOp.INTERSECT,
            id="step_c1",
        )
        combine2 = PlanStepNode(
            search_name=COMBINE_SEARCH_NAME,
            primary_input=combine1,
            secondary_input=step_c,
            operator=CombineOp.UNION,
            id="step_c2",
        )
        graph.steps = {
            s.id: s for s in [step_a, step_b, step_c, combine1, combine2]
        }
        graph.recompute_roots()

        result = graph.find_parent("step_c1")
        assert result is not None
        parent, slot = result
        assert parent.id == "step_c2"
        assert slot == "primary"


# ---------------------------------------------------------------------------
# insert_step_with_combine
# ---------------------------------------------------------------------------


class TestInsertStepWithCombine:
    def test_combine_with_root(self) -> None:
        """Combining with the sole root: combine becomes new root."""
        graph = _make_graph()
        step_a = _leaf("A", "step_a")
        graph.add_step(step_a)

        step_b = _leaf("B", "step_b")
        leaf_id, combine_id = graph.insert_step_with_combine(
            step_b, "step_a", CombineOp.INTERSECT
        )

        _assert_invariant(graph)
        assert leaf_id == "step_b"
        assert combine_id in graph.steps
        assert combine_id in graph.roots
        assert "step_a" not in graph.roots
        assert "step_b" not in graph.roots

        combine = graph.steps[combine_id]
        assert combine.primary_input is not None
        assert combine.primary_input.id == "step_a"
        assert combine.secondary_input is not None
        assert combine.secondary_input.id == "step_b"
        assert combine.operator == CombineOp.INTERSECT

    def test_combine_with_internal_node(self) -> None:
        """Combining with an internal (non-root) step inserts between step and parent."""
        graph = _make_graph()
        # Build: A -> combine1(A, B) [root]
        step_a = _leaf("A", "step_a")
        step_b = _leaf("B", "step_b")
        combine1 = PlanStepNode(
            search_name=COMBINE_SEARCH_NAME,
            primary_input=step_a,
            secondary_input=step_b,
            operator=CombineOp.INTERSECT,
            id="step_c1",
        )
        graph.steps = {s.id: s for s in [step_a, step_b, combine1]}
        graph.recompute_roots()
        assert graph.roots == {"step_c1"}

        # Insert D combining with A (an internal node)
        step_d = _leaf("D", "step_d")
        _, new_combine_id = graph.insert_step_with_combine(
            step_d, "step_a", CombineOp.UNION
        )

        _assert_invariant(graph)
        # Root should still be combine1
        assert "step_c1" in graph.roots
        # combine1.primary_input should now be the new combine, not A directly
        assert combine1.primary_input is not None
        assert combine1.primary_input.id == new_combine_id

        new_combine = graph.steps[new_combine_id]
        assert new_combine.primary_input is not None
        assert new_combine.primary_input.id == "step_a"
        assert new_combine.secondary_input is not None
        assert new_combine.secondary_input.id == "step_d"
        assert new_combine.operator == CombineOp.UNION

    def test_combine_with_secondary_input(self) -> None:
        """Combining with a step that is the secondary input of its parent."""
        graph = _make_graph()
        step_a = _leaf("A", "step_a")
        step_b = _leaf("B", "step_b")
        combine1 = PlanStepNode(
            search_name=COMBINE_SEARCH_NAME,
            primary_input=step_a,
            secondary_input=step_b,
            operator=CombineOp.INTERSECT,
            id="step_c1",
        )
        graph.steps = {s.id: s for s in [step_a, step_b, combine1]}
        graph.recompute_roots()

        # Insert E combining with B (secondary input of combine1)
        step_e = _leaf("E", "step_e")
        _, new_combine_id = graph.insert_step_with_combine(
            step_e, "step_b", CombineOp.MINUS
        )

        _assert_invariant(graph)
        # combine1.secondary_input should now be the new combine
        assert combine1.secondary_input is not None
        assert combine1.secondary_input.id == new_combine_id

        new_combine = graph.steps[new_combine_id]
        assert new_combine.primary_input is not None
        assert new_combine.primary_input.id == "step_b"
        assert new_combine.secondary_input is not None
        assert new_combine.secondary_input.id == "step_e"

    def test_custom_display_name(self) -> None:
        graph = _make_graph()
        step_a = _leaf("A", "step_a")
        graph.add_step(step_a)

        step_b = _leaf("B", "step_b")
        _, combine_id = graph.insert_step_with_combine(
            step_b, "step_a", CombineOp.INTERSECT, combine_display_name="My Combine"
        )

        combine = graph.steps[combine_id]
        assert combine.display_name == "My Combine"
        _assert_invariant(graph)

    def test_nonexistent_target_raises(self) -> None:
        graph = _make_graph()
        step_a = _leaf("A", "step_a")
        graph.add_step(step_a)

        step_b = _leaf("B", "step_b")
        with pytest.raises(KeyError, match="not_here"):
            graph.insert_step_with_combine(
                step_b, "not_here", CombineOp.INTERSECT
            )

    def test_steps_registered_in_graph(self) -> None:
        """Both the new leaf and the combine are in graph.steps."""
        graph = _make_graph()
        step_a = _leaf("A", "step_a")
        graph.add_step(step_a)

        step_b = _leaf("B", "step_b")
        leaf_id, combine_id = graph.insert_step_with_combine(
            step_b, "step_a", CombineOp.INTERSECT
        )

        assert leaf_id in graph.steps
        assert combine_id in graph.steps
        assert len(graph.steps) == 3  # A, B, combine

    def test_history_saved(self) -> None:
        """insert_step_with_combine saves a history snapshot."""
        graph = _make_graph()
        step_a = _leaf("A", "step_a")
        graph.add_step(step_a)
        graph.save_history("initial")

        step_b = _leaf("B", "step_b")
        graph.insert_step_with_combine(
            step_b, "step_a", CombineOp.INTERSECT
        )
        # The method itself saves history, so we should have at least 2 entries
        assert len(graph.history) >= 2


# ---------------------------------------------------------------------------
# delete_step_connected
# ---------------------------------------------------------------------------


class TestDeleteStepConnected:
    def test_delete_sole_step(self) -> None:
        """Deleting the only step empties the graph."""
        graph = _make_graph()
        step_a = _leaf("A", "step_a")
        graph.add_step(step_a)

        deleted = graph.delete_step_connected("step_a")

        assert deleted == ["step_a"]
        assert len(graph.steps) == 0
        assert len(graph.roots) == 0

    def test_delete_leaf_of_combine(self) -> None:
        """Delete leaf A from combine(A, B) → B becomes root, combine removed."""
        graph = _make_graph()
        step_a = _leaf("A", "step_a")
        step_b = _leaf("B", "step_b")
        combine = PlanStepNode(
            search_name=COMBINE_SEARCH_NAME,
            primary_input=step_a,
            secondary_input=step_b,
            operator=CombineOp.INTERSECT,
            id="step_c",
        )
        graph.steps = {s.id: s for s in [step_a, step_b, combine]}
        graph.recompute_roots()

        deleted = graph.delete_step_connected("step_a")

        _assert_invariant(graph)
        assert set(deleted) == {"step_a", "step_c"}
        assert "step_b" in graph.steps
        assert graph.roots == {"step_b"}
        assert "step_a" not in graph.steps
        assert "step_c" not in graph.steps

    def test_delete_secondary_leaf_of_combine(self) -> None:
        """Delete leaf B (secondary) from combine(A, B) → A becomes root."""
        graph = _make_graph()
        step_a = _leaf("A", "step_a")
        step_b = _leaf("B", "step_b")
        combine = PlanStepNode(
            search_name=COMBINE_SEARCH_NAME,
            primary_input=step_a,
            secondary_input=step_b,
            operator=CombineOp.INTERSECT,
            id="step_c",
        )
        graph.steps = {s.id: s for s in [step_a, step_b, combine]}
        graph.recompute_roots()

        deleted = graph.delete_step_connected("step_b")

        _assert_invariant(graph)
        assert set(deleted) == {"step_b", "step_c"}
        assert graph.steps.keys() == {"step_a"}
        assert graph.roots == {"step_a"}

    def test_delete_leaf_of_combine_with_grandparent(self) -> None:
        """
        Tree: combine2(combine1(A, B), C)
        Delete A → combine1 collapses, B reconnects to combine2.primary_input.
        """
        graph = _make_graph()
        step_a = _leaf("A", "step_a")
        step_b = _leaf("B", "step_b")
        step_c = _leaf("C", "step_c")
        combine1 = PlanStepNode(
            search_name=COMBINE_SEARCH_NAME,
            primary_input=step_a,
            secondary_input=step_b,
            operator=CombineOp.INTERSECT,
            id="step_c1",
        )
        combine2 = PlanStepNode(
            search_name=COMBINE_SEARCH_NAME,
            primary_input=combine1,
            secondary_input=step_c,
            operator=CombineOp.UNION,
            id="step_c2",
        )
        graph.steps = {
            s.id: s for s in [step_a, step_b, step_c, combine1, combine2]
        }
        graph.recompute_roots()

        deleted = graph.delete_step_connected("step_a")

        _assert_invariant(graph)
        assert set(deleted) == {"step_a", "step_c1"}
        # combine2 should now have B as primary input (replacing combine1)
        assert combine2.primary_input is not None
        assert combine2.primary_input.id == "step_b"
        assert graph.roots == {"step_c2"}

    def test_delete_transform(self) -> None:
        """Delete a transform → reconnect its input to its consumer."""
        graph = _make_graph()
        step_a = _leaf("A", "step_a")
        transform = PlanStepNode(
            search_name="GenesByOrthologPattern",
            primary_input=step_a,
            id="step_t",
        )
        graph.steps = {s.id: s for s in [step_a, transform]}
        graph.recompute_roots()
        assert graph.roots == {"step_t"}

        deleted = graph.delete_step_connected("step_t")

        _assert_invariant(graph)
        assert deleted == ["step_t"]
        assert graph.steps.keys() == {"step_a"}
        assert graph.roots == {"step_a"}

    def test_delete_transform_with_parent(self) -> None:
        """
        Tree: combine(transform(A), B)
        Delete transform → A reconnects to combine.primary_input.
        """
        graph = _make_graph()
        step_a = _leaf("A", "step_a")
        step_b = _leaf("B", "step_b")
        transform = PlanStepNode(
            search_name="GenesByOrthologPattern",
            primary_input=step_a,
            id="step_t",
        )
        combine = PlanStepNode(
            search_name=COMBINE_SEARCH_NAME,
            primary_input=transform,
            secondary_input=step_b,
            operator=CombineOp.INTERSECT,
            id="step_c",
        )
        graph.steps = {s.id: s for s in [step_a, step_b, transform, combine]}
        graph.recompute_roots()

        deleted = graph.delete_step_connected("step_t")

        _assert_invariant(graph)
        assert deleted == ["step_t"]
        assert combine.primary_input is not None
        assert combine.primary_input.id == "step_a"
        assert "step_t" not in graph.steps

    def test_delete_subtree_child_of_combine(self) -> None:
        """
        Tree: combine(combine_inner(A, B), C)
        Delete combine_inner → removes combine_inner + A + B, collapses outer combine, C becomes root.
        """
        graph = _make_graph()
        step_a = _leaf("A", "step_a")
        step_b = _leaf("B", "step_b")
        step_c = _leaf("C", "step_c")
        combine_inner = PlanStepNode(
            search_name=COMBINE_SEARCH_NAME,
            primary_input=step_a,
            secondary_input=step_b,
            operator=CombineOp.INTERSECT,
            id="step_ci",
        )
        combine_outer = PlanStepNode(
            search_name=COMBINE_SEARCH_NAME,
            primary_input=combine_inner,
            secondary_input=step_c,
            operator=CombineOp.UNION,
            id="step_co",
        )
        graph.steps = {
            s.id: s for s in [step_a, step_b, step_c, combine_inner, combine_outer]
        }
        graph.recompute_roots()

        graph.delete_step_connected("step_ci")

        _assert_invariant(graph)
        # combine_inner + A + B deleted, combine_outer collapsed, C remains
        assert "step_ci" not in graph.steps
        assert "step_a" not in graph.steps
        assert "step_b" not in graph.steps
        assert "step_co" not in graph.steps
        assert graph.steps.keys() == {"step_c"}
        assert graph.roots == {"step_c"}

    def test_delete_leaf_whose_parent_is_transform(self) -> None:
        """
        Tree: combine(transform(A), B)
        Delete A → transform has no input, cascades: transform deleted, combine collapses, B remains.
        """
        graph = _make_graph()
        step_a = _leaf("A", "step_a")
        step_b = _leaf("B", "step_b")
        transform = PlanStepNode(
            search_name="GenesByOrthologPattern",
            primary_input=step_a,
            id="step_t",
        )
        combine = PlanStepNode(
            search_name=COMBINE_SEARCH_NAME,
            primary_input=transform,
            secondary_input=step_b,
            operator=CombineOp.INTERSECT,
            id="step_c",
        )
        graph.steps = {s.id: s for s in [step_a, step_b, transform, combine]}
        graph.recompute_roots()

        graph.delete_step_connected("step_a")

        _assert_invariant(graph)
        assert "step_a" not in graph.steps
        assert "step_t" not in graph.steps
        assert "step_c" not in graph.steps
        assert graph.steps.keys() == {"step_b"}
        assert graph.roots == {"step_b"}

    def test_delete_root_combine(self) -> None:
        """
        Delete root combine(A, B) → need to pick a side to keep.
        We treat this as deleting the combine node itself (a combine kind),
        which collapses to primary side by default.
        """
        graph = _make_graph()
        step_a = _leaf("A", "step_a")
        step_b = _leaf("B", "step_b")
        combine = PlanStepNode(
            search_name=COMBINE_SEARCH_NAME,
            primary_input=step_a,
            secondary_input=step_b,
            operator=CombineOp.INTERSECT,
            id="step_c",
        )
        graph.steps = {s.id: s for s in [step_a, step_b, combine]}
        graph.recompute_roots()

        # Deleting the combine itself: keeps primary side (A), removes B + combine
        graph.delete_step_connected("step_c")

        _assert_invariant(graph)
        # When deleting a combine, we keep the primary subtree and delete secondary + combine
        assert "step_c" not in graph.steps
        assert "step_b" not in graph.steps
        assert graph.steps.keys() == {"step_a"}
        assert graph.roots == {"step_a"}

    def test_delete_nonexistent_returns_empty(self) -> None:
        graph = _make_graph()
        step_a = _leaf("A", "step_a")
        graph.add_step(step_a)

        deleted = graph.delete_step_connected("does_not_exist")

        assert deleted == []
        assert graph.steps.keys() == {"step_a"}
        _assert_invariant(graph)

    def test_delete_preserves_last_step_id(self) -> None:
        """After deletion, last_step_id is updated to the root (if any)."""
        graph = _make_graph()
        step_a = _leaf("A", "step_a")
        step_b = _leaf("B", "step_b")
        combine = PlanStepNode(
            search_name=COMBINE_SEARCH_NAME,
            primary_input=step_a,
            secondary_input=step_b,
            operator=CombineOp.INTERSECT,
            id="step_c",
        )
        graph.steps = {s.id: s for s in [step_a, step_b, combine]}
        graph.recompute_roots()
        graph.last_step_id = "step_c"

        graph.delete_step_connected("step_a")

        assert graph.last_step_id is not None
        assert graph.last_step_id in graph.steps


# ---------------------------------------------------------------------------
# add_step invariant assertion
# ---------------------------------------------------------------------------


class TestAddStepInvariant:
    def test_first_step_succeeds(self) -> None:
        graph = _make_graph()
        step_a = _leaf("A", "step_a")
        graph.add_step(step_a)
        _assert_invariant(graph)

    def test_second_disconnected_step_raises(self) -> None:
        """Adding a disconnected step to a non-empty graph violates the invariant."""
        graph = _make_graph()
        step_a = _leaf("A", "step_a")
        graph.add_step(step_a)

        step_b = _leaf("B", "step_b")
        with pytest.raises(ValueError, match="Single-root invariant"):
            graph.add_step(step_b)

    def test_combine_step_succeeds(self) -> None:
        """Adding a combine that consumes both roots is fine."""
        graph = _make_graph()
        step_a = _leaf("A", "step_a")
        # Bypass invariant for setup: add step_a, then step_b via insert_step_with_combine
        graph.add_step(step_a)

        step_b = _leaf("B", "step_b")
        graph.insert_step_with_combine(step_b, "step_a", CombineOp.INTERSECT)
        _assert_invariant(graph)
