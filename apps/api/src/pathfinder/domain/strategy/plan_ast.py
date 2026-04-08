"""Plan AST helpers — count nodes in plan trees."""

from pydantic import ValidationError

from pathfinder.domain.strategy.ast import PlanStepNode, walk_step_tree
from pathfinder.platform.types import JSONObject


def count_plan_nodes(plan: JSONObject) -> int:
    """Count step nodes in a plan dict.

    Accepts a raw dict (e.g. from the database) and validates the ``root``
    into a :class:`PlanStepNode` before counting.  Returns 0 for invalid data.
    """
    root_raw = plan.get("root")
    if not isinstance(root_raw, dict):
        return 0
    try:
        root = PlanStepNode.model_validate(root_raw)
    except ValidationError, TypeError, ValueError:
        return 0
    return len(walk_step_tree(root))
