"""Tree traversal and manipulation helpers for step analysis."""

from veupath_chatbot.domain.strategy.ast import PlanStepNode
from veupath_chatbot.domain.strategy.ops import CombineOp
from veupath_chatbot.domain.strategy.tree import (
    collect_plan_combine_nodes,
    collect_plan_leaves,
)


def _collect_leaves(tree: PlanStepNode) -> list[PlanStepNode]:
    """Return all leaf (search) nodes from the tree."""
    return collect_plan_leaves(tree)


def _collect_combine_nodes(tree: PlanStepNode) -> list[PlanStepNode]:
    """Return all combine (binary) nodes from the tree."""
    return collect_plan_combine_nodes(tree)


def _node_id(node: PlanStepNode) -> str:
    """Return the node's unique identifier."""
    return node.id


# ── Pruning internals ────────────────────────────────────────────────


def _prune_combine(
    node: PlanStepNode,
    pi: PlanStepNode,
    si: PlanStepNode,
    target_leaf_id: str,
) -> PlanStepNode | None:
    """Prune *target_leaf_id* from a combine node."""
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

    updates: dict[str, PlanStepNode] = {}
    if replacement_pi is not pi:
        updates["primary_input"] = replacement_pi
    if replacement_si is not si:
        updates["secondary_input"] = replacement_si
    if updates:
        return node.model_copy(update=updates)
    return node


def _prune_unary(
    node: PlanStepNode,
    pi: PlanStepNode,
    target_leaf_id: str,
) -> PlanStepNode | None:
    """Prune *target_leaf_id* from a unary (transform) node."""
    if pi.id == target_leaf_id:
        return None
    replacement = _prune_node(pi, target_leaf_id)
    if replacement is None:
        return None
    if replacement is not pi:
        return node.model_copy(update={"primary_input": replacement})
    return node


def _prune_node(node: PlanStepNode, target_leaf_id: str) -> PlanStepNode | None:
    """Recursively prune *target_leaf_id*, returning the replacement node.

    Returns ``None`` when the entire subtree collapses.
    """
    pi = node.primary_input
    si = node.secondary_input

    if pi is not None and si is not None:
        return _prune_combine(node, pi, si, target_leaf_id)

    if pi is not None:
        return _prune_unary(node, pi, target_leaf_id)

    return node


# ── Public helpers ───────────────────────────────────────────────────


def _remove_leaf_from_tree(
    tree: PlanStepNode,
    target_leaf_id: str,
) -> PlanStepNode | None:
    """Build a tree with *target_leaf_id* pruned out.

    When a leaf is removed its parent combine node is replaced by the
    surviving sibling subtree.  Transform nodes whose input collapses are
    also removed so the resulting tree always remains structurally valid.
    Returns ``None`` when the root itself is the target leaf (tree is empty).
    """
    if tree.id == target_leaf_id:
        return None
    return _prune_node(tree, target_leaf_id)


def _extract_leaf_branch(
    tree: PlanStepNode,
    leaf_id: str,
) -> PlanStepNode | None:
    """Extract the subtree that includes *leaf_id* and its ancestor transforms.

    Walks from the root toward *leaf_id*.  At combine nodes the function
    descends into the branch containing the leaf and returns it (unwrapped
    from the combine).  At transform/unary nodes it wraps the child result
    in the same transform.  This gives an isolated evaluation tree that
    respects the organism-conversion transforms above a leaf.

    Returns ``None`` if *leaf_id* is not found.
    """
    pi = tree.primary_input
    si = tree.secondary_input

    # Leaf node
    if pi is None and si is None:
        return tree if tree.id == leaf_id else None

    # Combine node: descend into whichever branch contains the leaf
    if pi is not None and si is not None:
        branch = _extract_leaf_branch(pi, leaf_id)
        if branch is not None:
            return branch
        return _extract_leaf_branch(si, leaf_id)

    # Transform/unary node: preserve the wrapper around the child result
    if pi is not None:
        child = _extract_leaf_branch(pi, leaf_id)
        if child is not None:
            return tree.model_copy(update={"primary_input": child})
        return None

    return None


def _build_subtree_with_operator(
    combine_node: PlanStepNode,
    operator: CombineOp,
) -> PlanStepNode:
    """Clone a combine node's subtree with a different operator."""
    return combine_node.model_copy(update={"operator": operator})
