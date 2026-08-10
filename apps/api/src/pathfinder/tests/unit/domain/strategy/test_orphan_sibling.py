"""Delete this branch, leave the combine and its other input floating.

This resolution was removed while the AST could hold only one root: orphaning
a combine produced a second component that ``to_strategy_ast`` could not
represent, so the delete pushed to WDK and then silently failed to persist.

``StrategyAst.detached_roots`` is that component's home. WDK still never sees
it - ``Step.java`` requires that a step with inputs belong to a strategy - and
"not pushed" is precisely what the dialog promises.
"""

from collections.abc import Iterable

import pytest

from pathfinder.domain.strategy.ast import StrategyStepNode, walk_step_tree
from pathfinder.domain.strategy.graph_model import flatten_tree
from pathfinder.domain.strategy.operations import DeleteResolution, DeleteStepOp
from pathfinder.domain.strategy.operations.apply import ApplyError, apply_operation
from pathfinder.domain.strategy.ops import CombineOp
from pathfinder.domain.strategy.session import StrategyGraph


def _graph_with(roots: Iterable[StrategyStepNode]) -> StrategyGraph:
    g = StrategyGraph(graph_id="g1", name="g", site_id="plasmodb")
    g.record_type = "transcript"
    for root in roots:
        g.steps.update(flatten_tree(root))
    g.recompute_roots()
    return g


def _leaf(id_: str) -> StrategyStepNode:
    return StrategyStepNode(id=id_, search_name="geneById")


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


def _orphan(step_id: str) -> DeleteStepOp:
    return DeleteStepOp(step_id=step_id, resolution=DeleteResolution.ORPHAN_SIBLING)


class TestWireContract:
    def test_the_resolution_exists(self) -> None:
        assert DeleteResolution("orphan-sibling") is DeleteResolution.ORPHAN_SIBLING

    def test_parses_from_the_wire(self) -> None:
        op = DeleteStepOp.model_validate(
            {"kind": "deleteStep", "stepId": "b", "resolution": "orphan-sibling"}
        )

        assert op.resolution == DeleteResolution.ORPHAN_SIBLING


class TestOrphanSibling:
    def test_deletes_only_the_targets_subtree(self) -> None:
        g = _graph_with([_combine("c", _leaf("a"), _leaf("b"))])

        result = apply_operation(g, _orphan("b"))

        assert "b" not in g.steps
        assert result.dropped_step_ids == ["b"]

    def test_keeps_the_combine_and_the_surviving_branch(self) -> None:
        g = _graph_with([_combine("c", _leaf("a"), _leaf("b"))])

        apply_operation(g, _orphan("b"))

        assert "c" in g.steps
        assert "a" in g.steps

    def test_clears_the_slot_that_pointed_at_the_target(self) -> None:
        g = _graph_with([_combine("c", _leaf("a"), _leaf("b"))])

        apply_operation(g, _orphan("b"))

        assert g.steps["c"].secondary_input_id is None
        assert g.steps["c"].operator is None

    def test_detaches_the_parent_from_its_own_parent(self) -> None:
        inner = _combine("c", _leaf("a"), _leaf("b"))
        outer = _combine("d", inner, _leaf("e"))
        g = _graph_with([outer])

        apply_operation(g, _orphan("b"))

        outer_node = g.steps["d"]
        assert outer_node.secondary_input_id is None
        assert outer_node.primary_input_id is not None
        assert outer_node.primary_input_id == "e"
        assert "c" in g.roots

    def test_the_orphaned_component_survives_serialization(self) -> None:
        """The whole reason this was pulled: the survivors used to have
        nowhere to live, so the delete was never written down."""
        inner = _combine("c", _leaf("a"), _leaf("b"))
        outer = _combine("d", inner, _leaf("e"))
        g = _graph_with([outer])

        apply_operation(g, _orphan("b"))
        ast = g.to_strategy_ast()

        assert ast is not None
        detached_ids = {node.id for node in ast.detached_roots}
        assert detached_ids == {"c"}

    def test_every_surviving_step_is_still_represented(self) -> None:
        inner = _combine("c", _leaf("a"), _leaf("b"))
        outer = _combine("d", inner, _leaf("e"))
        g = _graph_with([outer])

        apply_operation(g, _orphan("b"))
        ast = g.to_strategy_ast()

        assert ast is not None
        seen = {node.id for node in walk_step_tree(ast.root)}
        for detached in ast.detached_roots:
            seen |= {node.id for node in walk_step_tree(detached)}
        assert seen == {"a", "c", "d", "e"}

    def test_promotes_the_survivor_when_the_primary_slot_is_cleared(self) -> None:
        g = _graph_with([_combine("c", _leaf("a"), _leaf("b"))])

        apply_operation(g, _orphan("a"))

        node = g.steps["c"]
        assert node.primary_input_id is not None
        assert node.primary_input_id == "b"
        assert node.secondary_input_id is None

    def test_deletes_the_whole_subtree_under_the_target(self) -> None:
        deep = _combine("t", _leaf("t1"), _leaf("t2"))
        g = _graph_with([_combine("c", _leaf("a"), deep)])

        result = apply_operation(g, _orphan("t"))

        assert {"t", "t1", "t2"}.isdisjoint(g.steps)
        assert set(result.dropped_step_ids) == {"t", "t1", "t2"}

    def test_a_root_level_step_has_no_combine_parent(self) -> None:
        g = _graph_with([_leaf("a")])

        with pytest.raises(ApplyError):
            apply_operation(g, _orphan("a"))

    def test_unknown_step_is_rejected(self) -> None:
        g = _graph_with([_combine("c", _leaf("a"), _leaf("b"))])

        with pytest.raises(ApplyError):
            apply_operation(g, _orphan("missing"))
