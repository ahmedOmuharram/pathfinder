"""Strategy plan validation helpers."""

from veupath_chatbot.domain.strategy.ast import StrategyAST
from veupath_chatbot.domain.strategy.validate import validate_strategy
from veupath_chatbot.platform.errors import ValidationError
from veupath_chatbot.platform.types import JSONObject


def validate_plan_or_raise(plan: JSONObject) -> StrategyAST:
    """Parse and validate a strategy plan, raising typed ValidationError."""
    try:
        strategy_ast = StrategyAST.model_validate(plan)
    except Exception as exc:
        raise ValidationError(
            title="Invalid plan",
            errors=[
                {"path": "", "message": str(exc), "code": "INVALID_STRATEGY"},
            ],
        ) from exc

    validation = validate_strategy(strategy_ast)
    if not validation.valid:
        raise ValidationError(
            title="Invalid plan",
            errors=[
                {"path": err.path, "message": err.message, "code": err.code}
                for err in validation.errors
            ],
        )

    return strategy_ast
