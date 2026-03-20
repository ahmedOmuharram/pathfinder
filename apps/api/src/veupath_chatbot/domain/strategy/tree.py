"""Shared tree walkers for strategy trees.

Two families of trees appear throughout the codebase:

1. **Dict-based trees** -- raw WDK ``stepTree`` payloads or ``PlanStepNode.to_dict()``
   output.  Children live under ``"primaryInput"`` and ``"secondaryInput"`` keys.

2. **AST trees** -- :class:`PlanStepNode` objects with ``.primary_input`` /
   ``.secondary_input`` attributes.

This module provides generic, reusable walkers for both so that every call
site does not need to re-implement the recursive descent.
"""

from collections.abc import Callable

from veupath_chatbot.domain.strategy.ast import PlanStepNode
from veupath_chatbot.platform.types import JSONObject

# ── Dict-based tree walkers ───────────────────────────────────────────


def walk_dict_tree(root: object, visitor: Callable[[JSONObject], None]) -> None:
    """Pre-order walk of a dict-based step tree.

    Calls *visitor* on every node (the node dict itself), then recurses
    into ``primaryInput`` and ``secondaryInput`` when they are dicts.

    No-ops silently if *root* is not a dict.
    """
    if not isinstance(root, dict):
        return
    visitor(root)
    pi = root.get("primaryInput")
    if isinstance(pi, dict):
        walk_dict_tree(pi, visitor)
    si = root.get("secondaryInput")
    if isinstance(si, dict):
        walk_dict_tree(si, visitor)


def collect_dict_nodes(root: object) -> list[JSONObject]:
    """Collect all nodes in a dict-based tree (pre-order)."""
    nodes: list[JSONObject] = []
    walk_dict_tree(root, nodes.append)
    return nodes


def collect_dict_leaves(root: object) -> list[JSONObject]:
    """Collect leaf nodes (no primaryInput or secondaryInput) from a dict tree."""
    leaves: list[JSONObject] = []

    def _visit(node: JSONObject) -> None:
        pi = node.get("primaryInput")
        si = node.get("secondaryInput")
        if not isinstance(pi, dict) and not isinstance(si, dict):
            leaves.append(node)

    walk_dict_tree(root, _visit)
    return leaves


def collect_dict_combine_nodes(root: object) -> list[JSONObject]:
    """Collect combine (binary) nodes from a dict tree.

    A combine node has both ``primaryInput`` and ``secondaryInput`` as dicts.
    """
    combines: list[JSONObject] = []

    def _visit(node: JSONObject) -> None:
        pi = node.get("primaryInput")
        si = node.get("secondaryInput")
        if isinstance(pi, dict) and isinstance(si, dict):
            combines.append(node)

    walk_dict_tree(root, _visit)
    return combines


def count_dict_nodes(root: object) -> int:
    """Count all nodes in a dict-based tree."""
    if not isinstance(root, dict):
        return 0
    count = 1
    pi = root.get("primaryInput")
    if isinstance(pi, dict):
        count += count_dict_nodes(pi)
    si = root.get("secondaryInput")
    if isinstance(si, dict):
        count += count_dict_nodes(si)
    return count


def map_dict_tree(
    root: JSONObject,
    transform: Callable[[JSONObject], JSONObject],
) -> JSONObject:
    """Bottom-up map: apply *transform* to every node, children first.

    Children are replaced with their transformed versions before the
    parent is passed to *transform*.  The original tree is **not** mutated;
    each node dict is shallow-copied before transformation.
    """
    node = root.copy()

    pi = node.get("primaryInput")
    if isinstance(pi, dict):
        node["primaryInput"] = map_dict_tree(pi, transform)
    si = node.get("secondaryInput")
    if isinstance(si, dict):
        node["secondaryInput"] = map_dict_tree(si, transform)

    return transform(node)


# ── PlanStepNode (AST) walkers ────────────────────────────────────────


def walk_plan_tree(root: PlanStepNode, visitor: Callable[[PlanStepNode], None]) -> None:
    """Pre-order walk of a PlanStepNode AST.

    Calls *visitor* on every node, then recurses into
    ``.primary_input`` and ``.secondary_input``.
    """
    visitor(root)
    if root.primary_input is not None:
        walk_plan_tree(root.primary_input, visitor)
    if root.secondary_input is not None:
        walk_plan_tree(root.secondary_input, visitor)


def collect_plan_nodes(root: PlanStepNode) -> list[PlanStepNode]:
    """Collect all AST nodes (pre-order)."""
    nodes: list[PlanStepNode] = []
    walk_plan_tree(root, nodes.append)
    return nodes


def collect_plan_leaves(root: PlanStepNode) -> list[PlanStepNode]:
    """Collect leaf AST nodes (no primary or secondary input)."""
    leaves: list[PlanStepNode] = []

    def _visit(node: PlanStepNode) -> None:
        if node.primary_input is None and node.secondary_input is None:
            leaves.append(node)

    walk_plan_tree(root, _visit)
    return leaves
