"""Plan AST helpers — count nodes in plan trees."""

from pydantic import ValidationError

from veupath_chatbot.domain.strategy.ast import StrategyAST
from veupath_chatbot.platform.types import JSONObject


def count_plan_nodes(plan: JSONObject) -> int:
    """Count step nodes in a plan dict.

    Accepts a raw dict (e.g. from the database) and validates it into
    a :class:`StrategyAST` before counting.  Returns 0 for invalid data.
    """
    try:
        ast = StrategyAST.model_validate(plan)
    except (ValidationError, TypeError, ValueError):
        return 0
    return len(ast.get_all_steps())
