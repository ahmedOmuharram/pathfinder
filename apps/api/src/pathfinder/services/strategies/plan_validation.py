"""Strategy plan validation helpers."""

from pathfinder.domain.strategy.validate import validate_strategy
from pathfinder.platform.errors import ValidationError
from pathfinder.platform.types import JSONObject

from .schemas import StrategyPlanPayload


def validate_plan_or_raise(plan: JSONObject) -> StrategyPlanPayload:
    """Parse and validate a strategy plan, raising typed ValidationError."""
    try:
        payload = StrategyPlanPayload.model_validate(plan)
    except Exception as exc:
        raise ValidationError(
            title="Invalid plan",
            errors=[
                {"path": "", "message": str(exc), "code": "INVALID_STRATEGY"},
            ],
        ) from exc

    validation = validate_strategy(payload.root, payload.record_type)
    if not validation.valid:
        raise ValidationError(
            title="Invalid plan",
            errors=[
                {"path": err.path, "message": err.message, "code": err.code}
                for err in validation.errors
            ],
        )

    return payload
