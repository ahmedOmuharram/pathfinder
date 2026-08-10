"""Undo and redo on the graph canvas must reach the backend.

Ctrl+Z / Ctrl+Y replay a cached strategy by posting a ``replaceStrategy``
operation. The op existed in the union and the frontend reducer implemented
it, but ``apply_operation`` had no branch for it, so every undo fell through
to "unsupported operation" and rolled back with "Operation failed".

Replacing swaps the whole graph for the given tree: steps the tree does not
mention are gone, and the tree's own root becomes the graph's root.
"""

from collections.abc import Iterable

import pytest

from pathfinder.domain.strategy.ast import StrategyStepNode
from pathfinder.domain.strategy.graph_model import flatten_tree
from pathfinder.domain.strategy.operations import ReplaceStrategyOp
from pathfinder.domain.strategy.operations.apply import ApplyError, apply_operation
from pathfinder.domain.strategy.ops import CombineOp
from pathfinder.domain.strategy.session import StrategyGraph


def _graph_with(roots: Iterable[StrategyStepNode]) -> StrategyGraph:
    g = StrategyGraph(graph_id="g1", name="g", site_id="plasmodb")
    for root in roots:
        g.steps.update(flatten_tree(root))
    g.recompute_roots()
    return g


def _leaf(id_: str, search: str = "geneById") -> StrategyStepNode:
    return StrategyStepNode(id=id_, search_name=search)


def _combine(
    id_: str, primary: StrategyStepNode, secondary: StrategyStepNode
) -> StrategyStepNode:
    return StrategyStepNode(
        id=id_,
        search_name="__combine__",
        primary_input=primary,
        secondary_input=secondary,
        operator=CombineOp.INTERSECT,
    )


class TestReplaceStrategy:
    def test_the_operation_is_supported(self) -> None:
        g = _graph_with([_leaf("a")])

        apply_operation(g, ReplaceStrategyOp(root=_leaf("b")))

        assert "b" in g.steps

    def test_steps_absent_from_the_new_tree_are_dropped(self) -> None:
        g = _graph_with([_combine("c", _leaf("a"), _leaf("b"))])

        apply_operation(g, ReplaceStrategyOp(root=_leaf("a")))

        assert sorted(g.steps) == ["a"]

    def test_the_new_root_is_the_only_root(self) -> None:
        g = _graph_with([_leaf("a")])
        replacement = _combine("c", _leaf("x"), _leaf("y"))

        apply_operation(g, ReplaceStrategyOp(root=replacement))

        assert g.roots == {"c"}
        assert sorted(g.steps) == ["c", "x", "y"]

    def test_structure_is_recorded_as_id_references(self) -> None:
        """Steps reference each other by id, so editing one cannot reach into
        another. The old model stored the child object itself, which is what
        made the flat dict and the tree the same memory."""
        g = _graph_with([_leaf("a")])
        replacement = _combine("c", _leaf("x"), _leaf("y"))

        apply_operation(g, ReplaceStrategyOp(root=replacement))

        assert g.steps["c"].primary_input_id == "x"
        assert g.steps["c"].secondary_input_id == "y"
        assert "x" in g.steps
        assert "y" in g.steps

    def test_undo_round_trips_a_prior_shape(self) -> None:
        """What undo actually does: restore the tree captured before an edit."""
        original = _combine("c", _leaf("a"), _leaf("b"))
        g = _graph_with([original])
        before = g.to_strategy_ast()
        assert before is not None

        apply_operation(g, ReplaceStrategyOp(root=_leaf("a")))
        assert sorted(g.steps) == ["a"]

        apply_operation(g, ReplaceStrategyOp(root=before.root))

        assert sorted(g.steps) == ["a", "b", "c"]
        assert g.roots == {"c"}

    def test_reports_the_steps_it_dropped(self) -> None:
        g = _graph_with([_combine("c", _leaf("a"), _leaf("b"))])

        result = apply_operation(g, ReplaceStrategyOp(root=_leaf("a")))

        assert sorted(result.dropped_step_ids) == ["b", "c"]

    def test_name_and_description_are_applied_when_given(self) -> None:
        g = _graph_with([_leaf("a")])

        apply_operation(
            g,
            ReplaceStrategyOp(root=_leaf("a"), name="Renamed", description="why"),
        )

        assert g.name == "Renamed"
        assert g.description == "why"

    def test_metadata_is_left_alone_when_omitted(self) -> None:
        g = _graph_with([_leaf("a")])
        g.name = "Original"
        g.description = "keep me"

        apply_operation(g, ReplaceStrategyOp(root=_leaf("a")))

        assert g.name == "Original"
        assert g.description == "keep me"

    def test_a_tree_with_a_duplicated_step_id_is_rejected(self) -> None:
        """WDK requires a step to belong to one position; a duplicate id would
        corrupt the graph's flat index rather than fail on push."""
        shared = _leaf("dup")
        g = _graph_with([_leaf("a")])
        bad = StrategyStepNode(
            id="root",
            search_name="__combine__",
            primary_input=shared,
            secondary_input=_combine("mid", _leaf("other"), shared.model_copy()),
            operator=CombineOp.INTERSECT,
        )

        with pytest.raises(ApplyError):
            apply_operation(g, ReplaceStrategyOp(root=bad))
