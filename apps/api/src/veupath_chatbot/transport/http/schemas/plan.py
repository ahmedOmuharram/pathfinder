"""Strategy plan request/response DTOs."""

from pydantic import BaseModel

from veupath_chatbot.platform.types import JSONArray
from veupath_chatbot.transport.http.schemas.strategies import StrategyPlanPayload


class PlanNormalizeRequest(BaseModel):
    siteId: str
    plan: StrategyPlanPayload


class PlanNormalizeResponse(BaseModel):
    plan: StrategyPlanPayload
    warnings: JSONArray | None = None
