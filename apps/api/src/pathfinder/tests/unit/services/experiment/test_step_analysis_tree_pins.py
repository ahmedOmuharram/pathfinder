"""What leave-one-out pruning and branch extraction produce for one tree.

A pruned combine collapses to its surviving sibling, a transform whose input
goes away goes away too, and an untouched subtree is returned by identity.
"""

from __future__ import annotations

from pathfinder.domain.strategy.ast import COMBINE_SEARCH_NAME, StrategyStepNode
from pathfinder.domain.strategy.ops import CombineOp
from pathfinder.services.experiment.step_analysis._tree_utils import (
    _extract_leaf_branch,
    _remove_leaf_from_tree,
)


def _leaf(name: str, step_id: str) -> StrategyStepNode:
    return StrategyStepNode(id=step_id, search_name=name)


def _tree() -> StrategyStepNode:
    """``(orthologs(a) INTERSECT (b UNION c))``."""
    return StrategyStepNode(
        id="root",
        search_name=COMBINE_SEARCH_NAME,
        operator=CombineOp.INTERSECT,
        primary_input=StrategyStepNode(
            id="t",
            search_name="GenesByOrthologs",
            primary_input=_leaf("A", "a"),
        ),
        secondary_input=StrategyStepNode(
            id="inner",
            search_name=COMBINE_SEARCH_NAME,
            operator=CombineOp.UNION,
            primary_input=_leaf("B", "b"),
            secondary_input=_leaf("C", "c"),
        ),
    )


class TestRemovingALeaf:
    def test_removing_the_root_itself_empties_the_tree(self) -> None:
        assert _remove_leaf_from_tree(_leaf("A", "a"), "a") is None

    def test_a_leaf_under_a_transform_takes_the_transform_with_it(self) -> None:
        pruned = _remove_leaf_from_tree(_tree(), "a")

        assert pruned is not None
        assert pruned.id == "inner"
        assert pruned.operator is CombineOp.UNION

    def test_a_leaf_under_a_combine_leaves_its_sibling_in_place(self) -> None:
        pruned = _remove_leaf_from_tree(_tree(), "b")

        assert pruned is not None
        assert pruned.id == "root"
        assert pruned.secondary_input is not None
        assert pruned.secondary_input.id == "c"
        assert pruned.primary_input is not None
        assert pruned.primary_input.id == "t"

    def test_an_absent_leaf_returns_the_same_object(self) -> None:
        tree = _tree()

        assert _remove_leaf_from_tree(tree, "nothing") is tree

    def test_removing_the_only_leaf_of_a_transform_root_empties_it(self) -> None:
        root = StrategyStepNode(
            id="t", search_name="GenesByOrthologs", primary_input=_leaf("A", "a")
        )

        assert _remove_leaf_from_tree(root, "a") is None


class TestExtractingALeafBranch:
    def test_the_branch_keeps_the_transforms_above_the_leaf(self) -> None:
        branch = _extract_leaf_branch(_tree(), "a")

        assert branch is not None
        assert branch.id == "t"
        assert branch.primary_input is not None
        assert branch.primary_input.id == "a"

    def test_a_leaf_under_two_combines_extracts_alone(self) -> None:
        branch = _extract_leaf_branch(_tree(), "c")

        assert branch is not None
        assert branch.id == "c"
        assert branch.primary_input is None

    def test_an_absent_leaf_extracts_nothing(self) -> None:
        assert _extract_leaf_branch(_tree(), "nothing") is None

    def test_a_leaf_root_extracts_itself(self) -> None:
        root = _leaf("A", "a")

        assert _extract_leaf_branch(root, "a") is root
