"""Tree traversal and manipulation helpers for step analysis."""

from pathfinder.domain.strategy.ast import StrategyStepNode
from pathfinder.domain.strategy.ops import CombineOp
from pathfinder.domain.strategy.tree import (
    collect_plan_combine_nodes,
    collect_plan_leaves,
)


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


def _prune_combine(
    node: StrategyStepNode,
    pi: StrategyStepNode,
    si: StrategyStepNode,
    target_leaf_id: str,
) -> StrategyStepNode | None:
    """Prune the target leaf from a combine node."""
    if pi.id == target_leaf_id:
        return si
    if si.id == target_leaf_id:
        return pi

    replacement_pi = _prune_node(pi, target_leaf_id)
    replacement_si = _prune_node(si, target_leaf_id)

    if replacement_pi is None:
        return replacement_si
    if replacement_si is None:
        return replacement_pi

    updates: dict[str, StrategyStepNode] = {}
    if replacement_pi is not pi:
        updates["primary_input"] = replacement_pi
    if replacement_si is not si:
        updates["secondary_input"] = replacement_si
    if updates:
        return node.model_copy(update=updates)
    return node


def _prune_unary(
    node: StrategyStepNode,
    pi: StrategyStepNode,
    target_leaf_id: str,
) -> StrategyStepNode | None:
    """Prune the target leaf from a transform node."""
    if pi.id == target_leaf_id:
        return None
    replacement = _prune_node(pi, target_leaf_id)
    if replacement is None:
        return None
    if replacement is not pi:
        return node.model_copy(update={"primary_input": replacement})
    return node


def _prune_node(node: StrategyStepNode, target_leaf_id: str) -> StrategyStepNode | None:
    """Prune the target leaf and give the replacement node, or None if it collapses."""
    pi = node.primary_input
    si = node.secondary_input

    if pi is not None and si is not None:
        return _prune_combine(node, pi, si, target_leaf_id)

    if pi is not None:
        return _prune_unary(node, pi, target_leaf_id)

    return node


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
    return _prune_node(tree, target_leaf_id)


def _extract_leaf_branch(
    tree: StrategyStepNode,
    leaf_id: str,
) -> StrategyStepNode | None:
    """Extract the subtree that holds the leaf and the transforms above it.

    A combine node contributes only the branch that holds the leaf. A transform
    node stays, so the extracted tree evaluates the leaf in the same way.
    """
    pi = tree.primary_input
    si = tree.secondary_input

    if pi is None and si is None:
        return tree if tree.id == leaf_id else None

    # A combine node keeps the branch that holds the leaf.
    if pi is not None and si is not None:
        branch = _extract_leaf_branch(pi, leaf_id)
        if branch is not None:
            return branch
        return _extract_leaf_branch(si, leaf_id)

    # A transform node keeps its wrapper around the child result.
    if pi is not None:
        child = _extract_leaf_branch(pi, leaf_id)
        if child is not None:
            return tree.model_copy(update={"primary_input": child})
        return None

    return None


def _build_subtree_with_operator(
    combine_node: StrategyStepNode,
    operator: CombineOp,
) -> StrategyStepNode:
    """Clone a combine node's subtree with a different operator."""
    return combine_node.model_copy(update={"operator": operator})
