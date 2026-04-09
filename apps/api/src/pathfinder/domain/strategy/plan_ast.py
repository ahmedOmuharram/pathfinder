"""Plan AST helpers — count nodes in plan trees."""

from pathfinder.domain.strategy.ast import walk_step_tree
from pathfinder.domain.strategy.plan_payload import StrategyPlanPayload


def count_plan_nodes(payload: StrategyPlanPayload) -> int:
    """Count step nodes in a typed plan payload."""
    return len(walk_step_tree(payload.root))
