"""Typed tree walkers for StrategyStepNode strategy trees."""

from collections.abc import Callable

from pathfinder.domain.strategy.ast import StrategyStepNode


def walk_plan_tree(root: StrategyStepNode, visitor: Callable[[StrategyStepNode], None]) -> None:
    """Pre-order walk of a StrategyStepNode AST."""
    visitor(root)
    if root.primary_input is not None:
        walk_plan_tree(root.primary_input, visitor)
    if root.secondary_input is not None:
        walk_plan_tree(root.secondary_input, visitor)


def collect_plan_leaves(root: StrategyStepNode) -> list[StrategyStepNode]:
    """Collect leaf AST nodes (no primary or secondary input)."""
    leaves: list[StrategyStepNode] = []

    def _visit(node: StrategyStepNode) -> None:
        if node.primary_input is None and node.secondary_input is None:
            leaves.append(node)

    walk_plan_tree(root, _visit)
    return leaves


def collect_plan_combine_nodes(root: StrategyStepNode) -> list[StrategyStepNode]:
    """Collect combine (binary) nodes from a StrategyStepNode tree."""
    combines: list[StrategyStepNode] = []

    def _visit(node: StrategyStepNode) -> None:
        if node.primary_input is not None and node.secondary_input is not None:
            combines.append(node)

    walk_plan_tree(root, _visit)
    return combines


def map_plan_tree(
    root: StrategyStepNode,
    transform: Callable[[StrategyStepNode], StrategyStepNode],
) -> StrategyStepNode:
    """Bottom-up map: apply *transform* to every node, children first.

    The original tree is **not** mutated.
    """
    updated: dict[str, StrategyStepNode | None] = {}
    if root.primary_input is not None:
        updated["primary_input"] = map_plan_tree(root.primary_input, transform)
    if root.secondary_input is not None:
        updated["secondary_input"] = map_plan_tree(root.secondary_input, transform)
    node = root.model_copy(update=updated) if updated else root
    return transform(node)
