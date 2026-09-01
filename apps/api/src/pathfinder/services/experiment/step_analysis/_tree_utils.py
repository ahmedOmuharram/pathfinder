"""Tree traversal and manipulation helpers for step analysis."""

from pathfinder.domain.strategy.ast import StepFold, StrategyStepNode, fold_step_tree
from pathfinder.domain.strategy.ops import CombineOp
from pathfinder.domain.strategy.tree import (
    collect_plan_combine_nodes,
    collect_plan_leaves,
)

type _Rewrite = StepFold[StrategyStepNode | None]


def _collect_leaves(tree: StrategyStepNode) -> list[StrategyStepNode]:
    """Return all leaf (search) nodes from the tree."""
    return collect_plan_leaves(tree)


def _collect_combine_nodes(tree: StrategyStepNode) -> list[StrategyStepNode]:
    """Return all combine (binary) nodes from the tree."""
    return collect_plan_combine_nodes(tree)


def _node_id(node: StrategyStepNode) -> str:
    """Return the node's unique identifier."""
    return node.id


# Pruning internals


def _rewired(
    node: StrategyStepNode,
    primary: StrategyStepNode,
    secondary: StrategyStepNode,
) -> StrategyStepNode:
    """The combine with whichever slot changed, or the node itself."""
    updates: dict[str, StrategyStepNode] = {}
    if primary is not node.primary_input:
        updates["primary_input"] = primary
    if secondary is not node.secondary_input:
        updates["secondary_input"] = secondary
    return node.model_copy(update=updates) if updates else node


def _prune_combine(
    node: StrategyStepNode,
    primary: StrategyStepNode | None,
    secondary: StrategyStepNode | None,
    target_leaf_id: str,
) -> StrategyStepNode | None:
    """A combine that loses one input becomes the input it kept."""
    left, right = node.primary_input, node.secondary_input
    if left is not None and left.id == target_leaf_id:
        return right
    if right is not None and right.id == target_leaf_id:
        return left
    if primary is None:
        return secondary
    if secondary is None:
        return primary
    return _rewired(node, primary, secondary)


def _prune_unary(
    node: StrategyStepNode,
    primary: StrategyStepNode | None,
    target_leaf_id: str,
) -> StrategyStepNode | None:
    """A transform whose input goes away goes away with it."""
    left = node.primary_input
    if left is not None and left.id == target_leaf_id:
        return None
    if primary is None:
        return None
    if primary is left:
        return node
    return node.model_copy(update={"primary_input": primary})


def _pruned(target_leaf_id: str) -> _Rewrite:
    def fold(
        node: StrategyStepNode, inputs: list[StrategyStepNode | None]
    ) -> StrategyStepNode | None:
        if node.secondary_input is not None:
            return _prune_combine(node, inputs[0], inputs[1], target_leaf_id)
        if node.primary_input is not None:
            return _prune_unary(node, inputs[0], target_leaf_id)
        return node

    return fold


def _extracted(leaf_id: str) -> _Rewrite:
    def fold(
        node: StrategyStepNode, inputs: list[StrategyStepNode | None]
    ) -> StrategyStepNode | None:
        if node.secondary_input is not None:
            return inputs[0] if inputs[0] is not None else inputs[1]
        if node.primary_input is None:
            return node if node.id == leaf_id else None
        if inputs[0] is None:
            return None
        return node.model_copy(update={"primary_input": inputs[0]})

    return fold


# Public helpers


def _remove_leaf_from_tree(
    tree: StrategyStepNode,
    target_leaf_id: str,
) -> StrategyStepNode | None:
    """Build a tree without the target leaf.

    The surviving sibling replaces the parent combine node. A transform node
    whose input collapses goes away too. The result is None for an empty tree.
    """
    if tree.id == target_leaf_id:
        return None
    return fold_step_tree(tree, _pruned(target_leaf_id))


def _extract_leaf_branch(
    tree: StrategyStepNode,
    leaf_id: str,
) -> StrategyStepNode | None:
    """Extract the subtree that holds the leaf and the transforms above it.

    A combine node contributes only the branch that holds the leaf. A transform
    node stays, so the extracted tree evaluates the leaf in the same way.
    """
    return fold_step_tree(tree, _extracted(leaf_id))


def _build_subtree_with_operator(
    combine_node: StrategyStepNode,
    operator: CombineOp,
) -> StrategyStepNode:
    """Clone a combine node's subtree with a different operator."""
    return combine_node.model_copy(update={"operator": operator})
