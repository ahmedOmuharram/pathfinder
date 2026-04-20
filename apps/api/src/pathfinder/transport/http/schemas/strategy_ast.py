"""Strategy AST normalize request/response DTOs."""

from pathfinder.domain.strategy.strategy_ast import StrategyAst
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.platform.types import JSONArray


class StrategyAstNormalizeRequest(CamelModel):
    site_id: str
    strategy_ast: StrategyAst


class StrategyAstNormalizeResponse(CamelModel):
    strategy_ast: StrategyAst
    warnings: JSONArray | None = None

