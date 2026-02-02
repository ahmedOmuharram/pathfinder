"""Strategy plan validation helpers."""

from __future__ import annotations

from typing import Any

from veupath_chatbot.domain.strategy.ast import StrategyAST, from_dict
from veupath_chatbot.domain.strategy.validate import validate_strategy
from veupath_chatbot.platform.errors import ValidationError


def validate_plan_or_raise(plan: dict[str, Any]) -> StrategyAST:
    """Parse and validate a strategy plan, raising typed ValidationError."""
    try:
        strategy_ast = from_dict(plan)
    except Exception as exc:
        raise ValidationError(
            title="Invalid plan",
            errors=[
                {"path": "", "message": str(exc), "code": "INVALID_STRATEGY"},
            ],
        )

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
