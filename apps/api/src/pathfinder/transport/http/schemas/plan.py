"""Strategy plan request/response DTOs."""

from pydantic import BaseModel

from pathfinder.domain.strategy.plan_payload import StrategyPlanPayload
from pathfinder.platform.types import JSONArray


class PlanNormalizeRequest(BaseModel):
    siteId: str
    plan: StrategyPlanPayload


class PlanNormalizeResponse(BaseModel):
    plan: StrategyPlanPayload
    warnings: JSONArray | None = None
