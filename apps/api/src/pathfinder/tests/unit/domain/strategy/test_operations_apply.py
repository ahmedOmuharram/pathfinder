from collections.abc import Iterable

import pytest

from pathfinder.domain.strategy.ast import StrategyStepNode
from pathfinder.domain.strategy.operations import (
    AddCombineOp,
    AddLeafOp,
    AddTransformOp,
    AttachIntoSlot,
    AttachNewRoot,
    DeleteResolution,
    DeleteStepOp,
    DuplicateStepOp,
    ReplaceSubtreeOp,
    UpdateCombineOperatorOp,
    UpdateStepMetaOp,
    UpdateStepParamsOp,
    UpdateStrategyMetaOp,
)
from pathfinder.domain.strategy.operations.apply import ApplyError, apply_operation
from pathfinder.domain.strategy.ops import CombineOp
from pathfinder.domain.strategy.session import StrategyGraph


def _graph_with(roots: Iterable[StrategyStepNode]) -> StrategyGraph:
    g = StrategyGraph(graph_id="g1", name="g", site_id="plasmodb")
    for root in roots:
        stack = [root]
        while stack:
            node = stack.pop()
            g.steps[node.id] = node
            if node.primary_input is not None:
                stack.append(node.primary_input)
            if node.secondary_input is not None:
                stack.append(node.secondary_input)
    g.recompute_roots()
    return g


def _leaf(id_: str) -> StrategyStepNode:
    return StrategyStepNode(id=id_, search_name="geneById")


def _combine(id_: str, primary: StrategyStepNode, secondary: StrategyStepNode) -> StrategyStepNode:
    return StrategyStepNode(
        id=id_,
        search_name="__combine__",
        primary_input=primary,
        secondary_input=secondary,
        operator=CombineOp.INTERSECT,
    )


def _transform(id_: str, input_: StrategyStepNode) -> StrategyStepNode:
    return StrategyStepNode(id=id_, search_name="orthologs", primary_input=input_)


class TestApplyAddLeaf:
    def test_new_root(self) -> None:
        g = _graph_with([_leaf("a")])
        apply_operation(
            g,
            AddLeafOp(step=_leaf("b"), attach=AttachNewRoot()),
        )
        assert {"a", "b"} == set(g.steps.keys())
        assert g.roots == {"a", "b"}

    def test_into_slot(self) -> None:
        a = _leaf("a")
        b = _leaf("b")
        c = _combine("c", a, b)
        g = _graph_with([c])
        new_leaf = _leaf("d")
        apply_operation(
            g,
            AddLeafOp(
                step=new_leaf,
                attach=AttachIntoSlot(target_step_id="c", slot="primary"),
            ),
        )
        assert g.steps["c"].primary_input is new_leaf

    def test_rejects_duplicate_id(self) -> None:
        g = _graph_with([_leaf("a")])
        with pytest.raises(ApplyError):
            apply_operation(
                g,
                AddLeafOp(step=_leaf("a"), attach=AttachNewRoot()),
            )


class TestApplyAddCombine:
    def test_creates_combine(self) -> None:
        g = _graph_with([_leaf("a"), _leaf("b")])
        apply_operation(
            g,
            AddCombineOp(
                step=StrategyStepNode(
                    id="c", search_name="__combine__", operator=CombineOp.INTERSECT
                ),
                left_id="a",
                right_id="b",
            ),
        )
        c = g.steps["c"]
        assert c.primary_input is not None
        assert c.primary_input.id == "a"
        assert c.secondary_input is not None
        assert c.secondary_input.id == "b"
        assert g.roots == {"c"}

    def test_rejects_same_input(self) -> None:
        g = _graph_with([_leaf("a")])
        with pytest.raises(ApplyError):
            apply_operation(
                g,
                AddCombineOp(
                    step=StrategyStepNode(
                        id="c",
                        search_name="__combine__",
                        operator=CombineOp.INTERSECT,
                    ),
                    left_id="a",
                    right_id="a",
                ),
            )


class TestApplyAddTransform:
    def test_before_consumer_inserts_between(self) -> None:
        a = _leaf("a")
        r = StrategyStepNode(id="r", search_name="x", primary_input=a)
        g = _graph_with([r])
        apply_operation(
            g,
            AddTransformOp(
                step=StrategyStepNode(id="t", search_name="orthologs"),
                input_id="a",
                mode="before-consumer",
            ),
        )
        assert g.steps["r"].primary_input is not None
        assert g.steps["r"].primary_input.id == "t"
        assert g.steps["t"].primary_input is not None
        assert g.steps["t"].primary_input.id == "a"

    def test_new_root(self) -> None:
        g = _graph_with([_leaf("a")])
        apply_operation(
            g,
            AddTransformOp(
                step=StrategyStepNode(id="t", search_name="orthologs"),
                input_id="a",
                mode="new-root",
            ),
        )
        assert "t" in g.steps


class TestApplyDeleteStep:
    def test_collapse_combine_nested(self) -> None:
        a = _leaf("A")
        b = _leaf("B")
        d = _leaf("D")
        c = _combine("C", a, b)
        r = _combine("R", c, d)
        g = _graph_with([r])
        result = apply_operation(
            g,
            DeleteStepOp(step_id="A", resolution=DeleteResolution.COLLAPSE_COMBINE),
        )
        assert sorted(g.steps.keys()) == ["B", "D", "R"]
        assert g.steps["R"].primary_input is not None
        assert g.steps["R"].primary_input.id == "B"
        assert sorted(result.dropped_step_ids) == ["A", "C"]

    def test_collapse_combine_root(self) -> None:
        a = _leaf("a")
        b = _leaf("b")
        c = _combine("c", a, b)
        g = _graph_with([c])
        apply_operation(
            g,
            DeleteStepOp(step_id="a", resolution=DeleteResolution.COLLAPSE_COMBINE),
        )
        assert sorted(g.steps.keys()) == ["b"]

    def test_promote_primary(self) -> None:
        a = _leaf("a")
        b = _leaf("b")
        c = _combine("c", a, b)
        g = _graph_with([c])
        apply_operation(
            g,
            DeleteStepOp(step_id="c", resolution=DeleteResolution.PROMOTE_PRIMARY),
        )
        assert sorted(g.steps.keys()) == ["a"]

    def test_delete_subtree_through_transform_cascades(self) -> None:
        a = _leaf("a")
        t = _transform("t", a)
        r = StrategyStepNode(id="r", search_name="x", primary_input=t)
        g = _graph_with([r])
        apply_operation(
            g,
            DeleteStepOp(step_id="a", resolution=DeleteResolution.DELETE_SUBTREE),
        )
        assert sorted(g.steps.keys()) == ["r"]
        assert g.steps["r"].primary_input is None

    def test_delete_strategy_empties_graph(self) -> None:
        g = _graph_with([_leaf("a")])
        apply_operation(
            g,
            DeleteStepOp(step_id="a", resolution=DeleteResolution.DELETE_STRATEGY),
        )
        assert g.steps == {}
        assert g.roots == set()

    def test_unknown_step_raises(self) -> None:
        g = _graph_with([_leaf("a")])
        with pytest.raises(ApplyError):
            apply_operation(
                g,
                DeleteStepOp(
                    step_id="missing", resolution=DeleteResolution.DELETE_STRATEGY
                ),
            )


class TestApplyReplaceSubtree:
    def test_swaps_subtree_under_parent(self) -> None:
        a = _leaf("a")
        b = _leaf("b")
        c = _combine("c", a, b)
        g = _graph_with([c])
        new_a = _leaf("new_a")
        apply_operation(
            g,
            ReplaceSubtreeOp(step_id="a", subtree=new_a),
        )
        assert "a" not in g.steps
        assert "new_a" in g.steps
        assert g.steps["c"].primary_input is not None
        assert g.steps["c"].primary_input.id == "new_a"


class TestApplyUpdateOps:
    def test_update_step_params(self) -> None:
        g = _graph_with([_leaf("a")])
        apply_operation(
            g,
            UpdateStepParamsOp(step_id="a", parameters={"foo": "bar"}),
        )
        assert g.steps["a"].parameters == {"foo": "bar"}

    def test_update_combine_operator(self) -> None:
        a = _leaf("a")
        b = _leaf("b")
        c = _combine("c", a, b)
        g = _graph_with([c])
        apply_operation(
            g,
            UpdateCombineOperatorOp(
                step_id="c", operator=CombineOp.UNION, colocation_params=None
            ),
        )
        assert g.steps["c"].operator == CombineOp.UNION

    def test_update_step_meta(self) -> None:
        g = _graph_with([_leaf("a")])
        apply_operation(
            g,
            UpdateStepMetaOp(step_id="a", display_name="renamed"),
        )
        assert g.steps["a"].display_name == "renamed"

    def test_update_strategy_meta(self) -> None:
        g = _graph_with([_leaf("a")])
        apply_operation(
            g,
            UpdateStrategyMetaOp(name="New name", description="New description"),
        )
        assert g.name == "New name"
        assert g.description == "New description"


class TestApplyDuplicateStep:
    def test_duplicates_under_parent(self) -> None:
        a = _leaf("a")
        b = _leaf("b")
        c = _combine("c", a, b)
        g = _graph_with([c])
        apply_operation(
            g,
            DuplicateStepOp(
                source_step_id="a",
                duplicate_step_id="a_dup",
                combine_step_id="combine_dup",
            ),
        )
        assert "a_dup" in g.steps
        assert "combine_dup" in g.steps
        combine_dup = g.steps["combine_dup"]
        assert combine_dup.primary_input is not None
        assert combine_dup.primary_input.id == "a"
        assert combine_dup.secondary_input is not None
        assert combine_dup.secondary_input.id == "a_dup"
        # Original parent c now points at the new combine in place of a
        assert g.steps["c"].primary_input is not None
        assert g.steps["c"].primary_input.id == "combine_dup"

    def test_rejects_unknown_source(self) -> None:
        g = _graph_with([_leaf("a")])
        with pytest.raises(ApplyError, match="missing"):
            apply_operation(
                g,
                DuplicateStepOp(
                    source_step_id="missing",
                    duplicate_step_id="dup",
                    combine_step_id="cmb",
                ),
            )
