"""Typed tree walkers for PlanStepNode strategy trees."""

from collections.abc import Callable

from veupath_chatbot.domain.strategy.ast import PlanStepNode


def walk_plan_tree(root: PlanStepNode, visitor: Callable[[PlanStepNode], None]) -> None:
    """Pre-order walk of a PlanStepNode AST."""
    visitor(root)
    if root.primary_input is not None:
        walk_plan_tree(root.primary_input, visitor)
    if root.secondary_input is not None:
        walk_plan_tree(root.secondary_input, visitor)


def collect_plan_leaves(root: PlanStepNode) -> list[PlanStepNode]:
    """Collect leaf AST nodes (no primary or secondary input)."""
    leaves: list[PlanStepNode] = []

    def _visit(node: PlanStepNode) -> None:
        if node.primary_input is None and node.secondary_input is None:
            leaves.append(node)

    walk_plan_tree(root, _visit)
    return leaves


def collect_plan_combine_nodes(root: PlanStepNode) -> list[PlanStepNode]:
    """Collect combine (binary) nodes from a PlanStepNode tree."""
    combines: list[PlanStepNode] = []

    def _visit(node: PlanStepNode) -> None:
        if node.primary_input is not None and node.secondary_input is not None:
            combines.append(node)

    walk_plan_tree(root, _visit)
    return combines


def map_plan_tree(
    root: PlanStepNode,
    transform: Callable[[PlanStepNode], PlanStepNode],
) -> PlanStepNode:
    """Bottom-up map: apply *transform* to every node, children first.

    The original tree is **not** mutated.
    """
    updated: dict[str, PlanStepNode | None] = {}
    if root.primary_input is not None:
        updated["primary_input"] = map_plan_tree(root.primary_input, transform)
    if root.secondary_input is not None:
        updated["secondary_input"] = map_plan_tree(root.secondary_input, transform)
    node = root.model_copy(update=updated) if updated else root
    return transform(node)
