"""Tree traversal and manipulation helpers for step analysis."""

from __future__ import annotations

import copy

from veupath_chatbot.platform.types import JSONObject


def _collect_leaves(tree: JSONObject) -> list[JSONObject]:
    """Return all leaf (search) nodes from the tree."""
    leaves: list[JSONObject] = []
    pi = tree.get("primaryInput")
    si = tree.get("secondaryInput")
    if not isinstance(pi, dict) and not isinstance(si, dict):
        leaves.append(tree)
    if isinstance(pi, dict):
        leaves.extend(_collect_leaves(pi))
    if isinstance(si, dict):
        leaves.extend(_collect_leaves(si))
    return leaves


def _collect_combine_nodes(tree: JSONObject) -> list[JSONObject]:
    """Return all combine (binary) nodes from the tree."""
    nodes: list[JSONObject] = []
    pi = tree.get("primaryInput")
    si = tree.get("secondaryInput")
    if isinstance(pi, dict) and isinstance(si, dict):
        nodes.append(tree)
    if isinstance(pi, dict):
        nodes.extend(_collect_combine_nodes(pi))
    if isinstance(si, dict):
        nodes.extend(_collect_combine_nodes(si))
    return nodes


def _node_id(node: JSONObject) -> str:
    return str(node.get("id", node.get("searchName", "?")))


def _remove_leaf_from_tree(
    tree: JSONObject,
    target_leaf_id: str,
) -> JSONObject | None:
    """Build a tree with *target_leaf_id* pruned out.

    When a leaf is removed its parent combine node is replaced by the
    surviving sibling subtree.  Transform nodes whose input collapses are
    also removed so the resulting tree always remains structurally valid.
    Returns ``None`` when the root itself is the target leaf (tree is empty).
    """
    root_id = _node_id(tree)
    if root_id == target_leaf_id:
        return None

    out = copy.deepcopy(tree)

    def _prune(node: JSONObject) -> JSONObject | None:
        """Recursively prune *target_leaf_id*, returning the replacement node.

        Returns ``None`` when the entire subtree collapses (e.g. the only
        remaining content was the removed leaf).
        """
        pi = node.get("primaryInput")
        si = node.get("secondaryInput")

        if isinstance(pi, dict) and isinstance(si, dict):
            # --- Combine node ---
            pi_id = _node_id(pi)
            si_id = _node_id(si)
            if pi_id == target_leaf_id:
                return si
            if si_id == target_leaf_id:
                return pi

            replacement_pi = _prune(pi)
            replacement_si = _prune(si)

            if replacement_pi is None:
                return replacement_si
            if replacement_si is None:
                return replacement_pi

            if replacement_pi is not pi:
                node["primaryInput"] = replacement_pi
            if replacement_si is not si:
                node["secondaryInput"] = replacement_si
            return node

        if isinstance(pi, dict):
            # --- Transform / unary node ---
            pi_id = _node_id(pi)
            if pi_id == target_leaf_id:
                return None
            replacement = _prune(pi)
            if replacement is None:
                return None
            if replacement is not pi:
                node["primaryInput"] = replacement
            return node

        return node

    result = _prune(out)
    return result


def _extract_leaf_branch(tree: JSONObject, leaf_id: str) -> JSONObject | None:
    """Extract the subtree that includes *leaf_id* and its ancestor transforms.

    Walks from the root toward *leaf_id*.  At combine nodes the function
    descends into the branch containing the leaf and returns it (unwrapped
    from the combine).  At transform/unary nodes it wraps the child result
    in the same transform.  This gives an isolated evaluation tree that
    respects the organism-conversion transforms above a leaf.

    Returns ``None`` if *leaf_id* is not found.
    """
    pi = tree.get("primaryInput")
    si = tree.get("secondaryInput")

    if not isinstance(pi, dict) and not isinstance(si, dict):
        return copy.deepcopy(tree) if _node_id(tree) == leaf_id else None

    if isinstance(pi, dict) and isinstance(si, dict):
        branch = _extract_leaf_branch(pi, leaf_id)
        if branch is not None:
            return branch
        return _extract_leaf_branch(si, leaf_id)

    if isinstance(pi, dict):
        child = _extract_leaf_branch(pi, leaf_id)
        if child is not None:
            out = copy.deepcopy(tree)
            out["primaryInput"] = child
            return out
        return None

    return None


def _build_subtree_with_operator(
    combine_node: JSONObject,
    operator: str,
) -> JSONObject:
    """Clone a combine node's subtree with a different operator."""
    out = copy.deepcopy(combine_node)
    out["operator"] = operator
    return out
