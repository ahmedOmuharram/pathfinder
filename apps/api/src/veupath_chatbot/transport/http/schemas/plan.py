"""Strategy plan request/response DTOs."""

from pydantic import BaseModel

from veupath_chatbot.domain.strategy.ast import StrategyAST
from veupath_chatbot.platform.types import JSONArray


class PlanNormalizeRequest(BaseModel):
    siteId: str
    plan: StrategyAST


class PlanNormalizeResponse(BaseModel):
    plan: StrategyAST
    warnings: JSONArray | None = None
