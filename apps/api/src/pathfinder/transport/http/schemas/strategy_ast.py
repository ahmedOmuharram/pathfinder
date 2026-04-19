"""Strategy AST normalize request/response DTOs."""

from pydantic import BaseModel, Field

from pathfinder.domain.strategy.strategy_ast import StrategyAst
from pathfinder.platform.types import JSONArray


class StrategyAstNormalizeRequest(BaseModel):
    site_id: str = Field(alias="siteId")
    strategy_ast: StrategyAst = Field(alias="strategyAst")

    model_config = {"populate_by_name": True}


class StrategyAstNormalizeResponse(BaseModel):
    strategy_ast: StrategyAst = Field(alias="strategyAst")
    warnings: JSONArray | None = None

    model_config = {"populate_by_name": True}
