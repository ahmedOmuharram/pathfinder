"""Tests for domain.strategy.tree -- shared tree walkers."""

import copy

from veupath_chatbot.domain.strategy.ast import PlanStepNode
from veupath_chatbot.domain.strategy.ops import CombineOp
from veupath_chatbot.domain.strategy.tree import (
    collect_dict_leaves,
    collect_dict_nodes,
    collect_plan_leaves,
    collect_plan_nodes,
    count_dict_nodes,
    map_dict_tree,
    walk_dict_tree,
    walk_plan_tree,
)

# ---------------------------------------------------------------------------
# Fixtures: dict-based trees (WDK / PlanStepNode dicts)
# ---------------------------------------------------------------------------


def _leaf(lid: str, search: str = "") -> dict:
    return {"id": lid, "searchName": search or f"Search_{lid}"}


def _combine(nid: str, primary: dict, secondary: dict, op: str = "INTERSECT") -> dict:
    return {
        "id": nid,
        "operator": op,
        "primaryInput": primary,
        "secondaryInput": secondary,
    }


def _transform(nid: str, child: dict, search: str = "GenesByOrthologs") -> dict:
    return {"id": nid, "searchName": search, "primaryInput": child}


# ---------------------------------------------------------------------------
# Fixtures: PlanStepNode trees (AST)
# ---------------------------------------------------------------------------


def _ast_leaf(lid: str, search: str = "") -> PlanStepNode:
    return PlanStepNode(
        search_name=search or f"Search_{lid}",
        id=lid,
    )


def _ast_combine(
    nid: str, primary: PlanStepNode, secondary: PlanStepNode
) -> PlanStepNode:
    return PlanStepNode(
        search_name="boolean_question",
        primary_input=primary,
        secondary_input=secondary,
        operator=CombineOp.INTERSECT,
        id=nid,
    )


def _ast_transform(nid: str, child: PlanStepNode) -> PlanStepNode:
    return PlanStepNode(
        search_name="GenesByOrthologs",
        primary_input=child,
        id=nid,
    )


# =========================================================================
# walk_dict_tree
# =========================================================================


class TestWalkDictTree:
    def test_single_leaf(self) -> None:
        visited: list[str] = []
        walk_dict_tree(_leaf("L1"), lambda n: visited.append(str(n["id"])))
        assert visited == ["L1"]

    def test_combine_visits_all(self) -> None:
        tree = _combine("C1", _leaf("L1"), _leaf("L2"))
        visited: list[str] = []
        walk_dict_tree(tree, lambda n: visited.append(str(n["id"])))
        # Pre-order: root first, then primary, then secondary
        assert visited == ["C1", "L1", "L2"]

    def test_deep_tree(self) -> None:
        inner = _combine("C2", _leaf("L1"), _leaf("L2"))
        tree = _combine("C1", inner, _leaf("L3"))
        visited: list[str] = []
        walk_dict_tree(tree, lambda n: visited.append(str(n["id"])))
        assert visited == ["C1", "C2", "L1", "L2", "L3"]

    def test_transform_visits_parent_and_child(self) -> None:
        tree = _transform("T1", _leaf("L1"))
        visited: list[str] = []
        walk_dict_tree(tree, lambda n: visited.append(str(n["id"])))
        assert visited == ["T1", "L1"]

    def test_non_dict_is_no_op(self) -> None:
        visited: list[str] = []
        walk_dict_tree(42, lambda n: visited.append(str(n)))  # type: ignore[arg-type]
        assert visited == []


# =========================================================================
# collect_dict_nodes / collect_dict_leaves
# =========================================================================


class TestCollectDictNodes:
    def test_single_leaf(self) -> None:
        nodes = collect_dict_nodes(_leaf("L1"))
        assert len(nodes) == 1

    def test_combine_collects_all(self) -> None:
        tree = _combine("C1", _leaf("L1"), _leaf("L2"))
        nodes = collect_dict_nodes(tree)
        ids = {str(n["id"]) for n in nodes}
        assert ids == {"C1", "L1", "L2"}

    def test_deep_tree_collects_five(self) -> None:
        inner = _combine("C2", _leaf("L1"), _leaf("L2"))
        tree = _combine("C1", inner, _leaf("L3"))
        assert len(collect_dict_nodes(tree)) == 5


class TestCollectDictLeaves:
    def test_single_leaf(self) -> None:
        leaves = collect_dict_leaves(_leaf("L1"))
        assert len(leaves) == 1

    def test_combine_two_leaves(self) -> None:
        tree = _combine("C1", _leaf("L1"), _leaf("L2"))
        leaves = collect_dict_leaves(tree)
        ids = {str(n["id"]) for n in leaves}
        assert ids == {"L1", "L2"}

    def test_transform_leaf_is_inner_node(self) -> None:
        tree = _transform("T1", _leaf("L1"))
        leaves = collect_dict_leaves(tree)
        assert len(leaves) == 1
        assert leaves[0]["id"] == "L1"

    def test_deep_tree_three_leaves(self) -> None:
        inner = _combine("C2", _leaf("L1"), _leaf("L2"))
        tree = _combine("C1", inner, _leaf("L3"))
        leaves = collect_dict_leaves(tree)
        ids = {str(n["id"]) for n in leaves}
        assert ids == {"L1", "L2", "L3"}

    def test_combine_not_in_leaves(self) -> None:
        tree = _combine("C1", _leaf("L1"), _leaf("L2"))
        leaves = collect_dict_leaves(tree)
        ids = {str(n["id"]) for n in leaves}
        assert "C1" not in ids


# =========================================================================
# count_dict_nodes
# =========================================================================


class TestCountDictNodes:
    def test_single_leaf(self) -> None:
        assert count_dict_nodes(_leaf("L1")) == 1

    def test_combine(self) -> None:
        tree = _combine("C1", _leaf("L1"), _leaf("L2"))
        assert count_dict_nodes(tree) == 3

    def test_deep_tree(self) -> None:
        inner = _combine("C2", _leaf("L1"), _leaf("L2"))
        tree = _combine("C1", inner, _leaf("L3"))
        assert count_dict_nodes(tree) == 5

    def test_non_dict_returns_zero(self) -> None:
        assert count_dict_nodes("not a dict") == 0  # type: ignore[arg-type]
        assert count_dict_nodes(None) == 0  # type: ignore[arg-type]


# =========================================================================
# map_dict_tree
# =========================================================================


class TestMapDictTree:
    def test_identity(self) -> None:
        tree = _combine("C1", _leaf("L1"), _leaf("L2"))
        result = map_dict_tree(tree, lambda n: n)
        assert result["id"] == "C1"
        assert result["primaryInput"]["id"] == "L1"

    def test_transform_nodes(self) -> None:
        """Add a 'visited' key to every node."""
        tree = _combine("C1", _leaf("L1"), _leaf("L2"))

        def add_flag(n: dict) -> dict:
            n["visited"] = True
            return n

        result = map_dict_tree(tree, add_flag)
        assert result.get("visited") is True
        assert result["primaryInput"].get("visited") is True
        assert result["secondaryInput"].get("visited") is True

    def test_does_not_mutate_original(self) -> None:
        tree = _combine("C1", _leaf("L1"), _leaf("L2"))

        def rename(n: dict) -> dict:
            out = copy.copy(n)
            out["id"] = "X_" + str(out["id"])
            return out

        result = map_dict_tree(tree, rename)
        assert result["id"] == "X_C1"
        assert tree["id"] == "C1"  # original unchanged


# =========================================================================
# walk_plan_tree
# =========================================================================


class TestWalkPlanTree:
    def test_single_leaf(self) -> None:
        visited: list[str] = []
        walk_plan_tree(_ast_leaf("L1"), lambda n: visited.append(n.id))
        assert visited == ["L1"]

    def test_combine(self) -> None:
        tree = _ast_combine("C1", _ast_leaf("L1"), _ast_leaf("L2"))
        visited: list[str] = []
        walk_plan_tree(tree, lambda n: visited.append(n.id))
        assert visited == ["C1", "L1", "L2"]

    def test_deep_tree(self) -> None:
        inner = _ast_combine("C2", _ast_leaf("L1"), _ast_leaf("L2"))
        tree = _ast_combine("C1", inner, _ast_leaf("L3"))
        visited: list[str] = []
        walk_plan_tree(tree, lambda n: visited.append(n.id))
        assert visited == ["C1", "C2", "L1", "L2", "L3"]

    def test_transform(self) -> None:
        tree = _ast_transform("T1", _ast_leaf("L1"))
        visited: list[str] = []
        walk_plan_tree(tree, lambda n: visited.append(n.id))
        assert visited == ["T1", "L1"]


# =========================================================================
# collect_plan_nodes / collect_plan_leaves
# =========================================================================


class TestCollectPlanNodes:
    def test_collects_all(self) -> None:
        inner = _ast_combine("C2", _ast_leaf("L1"), _ast_leaf("L2"))
        tree = _ast_combine("C1", inner, _ast_leaf("L3"))
        nodes = collect_plan_nodes(tree)
        assert len(nodes) == 5

    def test_single_leaf(self) -> None:
        assert len(collect_plan_nodes(_ast_leaf("L1"))) == 1


class TestCollectPlanLeaves:
    def test_single_leaf(self) -> None:
        leaves = collect_plan_leaves(_ast_leaf("L1"))
        assert len(leaves) == 1
        assert leaves[0].id == "L1"

    def test_combine(self) -> None:
        tree = _ast_combine("C1", _ast_leaf("L1"), _ast_leaf("L2"))
        leaves = collect_plan_leaves(tree)
        ids = {n.id for n in leaves}
        assert ids == {"L1", "L2"}

    def test_transform_returns_inner_leaf(self) -> None:
        tree = _ast_transform("T1", _ast_leaf("L1"))
        leaves = collect_plan_leaves(tree)
        assert len(leaves) == 1
        assert leaves[0].id == "L1"

    def test_deep_tree(self) -> None:
        inner = _ast_combine("C2", _ast_leaf("L1"), _ast_leaf("L2"))
        tree = _ast_combine("C1", inner, _ast_leaf("L3"))
        leaves = collect_plan_leaves(tree)
        ids = {n.id for n in leaves}
        assert ids == {"L1", "L2", "L3"}
