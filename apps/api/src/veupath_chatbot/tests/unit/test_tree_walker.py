"""Tests for domain.strategy.tree -- typed PlanStepNode tree walkers."""

from veupath_chatbot.domain.strategy.ast import PlanStepNode
from veupath_chatbot.domain.strategy.ops import CombineOp
from veupath_chatbot.domain.strategy.tree import (
    collect_plan_combine_nodes,
    collect_plan_leaves,
    map_plan_tree,
    walk_plan_tree,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _leaf(lid: str, search: str = "") -> PlanStepNode:
    return PlanStepNode(search_name=search or f"Search_{lid}", id=lid)


def _combine(nid: str, primary: PlanStepNode, secondary: PlanStepNode) -> PlanStepNode:
    return PlanStepNode(
        search_name="boolean_question",
        primary_input=primary,
        secondary_input=secondary,
        operator=CombineOp.INTERSECT,
        id=nid,
    )


def _transform(nid: str, child: PlanStepNode) -> PlanStepNode:
    return PlanStepNode(
        search_name="GenesByOrthologs",
        primary_input=child,
        id=nid,
    )


# =========================================================================
# walk_plan_tree
# =========================================================================


class TestWalkPlanTree:
    def test_single_leaf(self) -> None:
        visited: list[str] = []
        walk_plan_tree(_leaf("L1"), lambda n: visited.append(n.id))
        assert visited == ["L1"]

    def test_combine(self) -> None:
        tree = _combine("C1", _leaf("L1"), _leaf("L2"))
        visited: list[str] = []
        walk_plan_tree(tree, lambda n: visited.append(n.id))
        assert visited == ["C1", "L1", "L2"]

    def test_deep_tree(self) -> None:
        inner = _combine("C2", _leaf("L1"), _leaf("L2"))
        tree = _combine("C1", inner, _leaf("L3"))
        visited: list[str] = []
        walk_plan_tree(tree, lambda n: visited.append(n.id))
        assert visited == ["C1", "C2", "L1", "L2", "L3"]

    def test_transform(self) -> None:
        tree = _transform("T1", _leaf("L1"))
        visited: list[str] = []
        walk_plan_tree(tree, lambda n: visited.append(n.id))
        assert visited == ["T1", "L1"]


# =========================================================================
# collect_plan_leaves
# =========================================================================


class TestCollectPlanLeaves:
    def test_single_leaf(self) -> None:
        leaves = collect_plan_leaves(_leaf("L1"))
        assert len(leaves) == 1
        assert leaves[0].id == "L1"

    def test_combine(self) -> None:
        tree = _combine("C1", _leaf("L1"), _leaf("L2"))
        ids = {n.id for n in collect_plan_leaves(tree)}
        assert ids == {"L1", "L2"}

    def test_transform_returns_inner_leaf(self) -> None:
        tree = _transform("T1", _leaf("L1"))
        leaves = collect_plan_leaves(tree)
        assert len(leaves) == 1
        assert leaves[0].id == "L1"

    def test_deep_tree(self) -> None:
        inner = _combine("C2", _leaf("L1"), _leaf("L2"))
        tree = _combine("C1", inner, _leaf("L3"))
        ids = {n.id for n in collect_plan_leaves(tree)}
        assert ids == {"L1", "L2", "L3"}


# =========================================================================
# collect_plan_combine_nodes
# =========================================================================


class TestCollectPlanCombineNodes:
    def test_single_leaf_has_no_combines(self) -> None:
        assert collect_plan_combine_nodes(_leaf("L1")) == []

    def test_single_combine(self) -> None:
        tree = _combine("C1", _leaf("L1"), _leaf("L2"))
        combines = collect_plan_combine_nodes(tree)
        assert len(combines) == 1
        assert combines[0].id == "C1"

    def test_nested_combines(self) -> None:
        inner = _combine("C2", _leaf("L1"), _leaf("L2"))
        tree = _combine("C1", inner, _leaf("L3"))
        ids = {n.id for n in collect_plan_combine_nodes(tree)}
        assert ids == {"C1", "C2"}

    def test_transform_not_a_combine(self) -> None:
        tree = _transform("T1", _leaf("L1"))
        assert collect_plan_combine_nodes(tree) == []


# =========================================================================
# map_plan_tree
# =========================================================================


class TestMapPlanTree:
    def test_identity(self) -> None:
        tree = _combine("C1", _leaf("L1"), _leaf("L2"))
        result = map_plan_tree(tree, lambda n: n)
        assert result.id == "C1"
        assert result.primary_input is not None
        assert result.primary_input.id == "L1"

    def test_transform_nodes(self) -> None:
        tree = _combine("C1", _leaf("L1"), _leaf("L2"))
        result = map_plan_tree(
            tree,
            lambda n: n.model_copy(update={"display_name": f"visited_{n.id}"}),
        )
        assert result.display_name == "visited_C1"
        assert result.primary_input is not None
        assert result.primary_input.display_name == "visited_L1"

    def test_does_not_mutate_original(self) -> None:
        tree = _combine("C1", _leaf("L1"), _leaf("L2"))
        result = map_plan_tree(
            tree,
            lambda n: n.model_copy(update={"display_name": "X"}),
        )
        assert result.display_name == "X"
        assert tree.display_name is None
