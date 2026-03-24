"""Strategy plan request/response DTOs."""

from pydantic import BaseModel

from veupath_chatbot.platform.types import JSONArray
from veupath_chatbot.services.strategies.schemas import StrategyPlanPayload


class PlanNormalizeRequest(BaseModel):
    siteId: str
    plan: StrategyPlanPayload


class PlanNormalizeResponse(BaseModel):
    plan: StrategyPlanPayload
    warnings: JSONArray | None = None
