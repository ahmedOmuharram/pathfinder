"""Strategy plan request/response DTOs."""

from pydantic import BaseModel

from pathfinder.platform.types import JSONArray
from pathfinder.services.strategies.schemas import StrategyPlanPayload


class PlanNormalizeRequest(BaseModel):
    siteId: str
    plan: StrategyPlanPayload


class PlanNormalizeResponse(BaseModel):
    plan: StrategyPlanPayload
    warnings: JSONArray | None = None
