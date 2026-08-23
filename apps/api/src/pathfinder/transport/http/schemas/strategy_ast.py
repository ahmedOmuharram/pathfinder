"""Strategy AST normalize request/response DTOs."""

from assistant_core.platform.pydantic_base import CamelModel
from assistant_core.platform.types import JSONArray

from pathfinder.domain.strategy.strategy_ast import StrategyAst


class StrategyAstNormalizeRequest(CamelModel):
    site_id: str
    strategy_ast: StrategyAst


class StrategyAstNormalizeResponse(CamelModel):
    strategy_ast: StrategyAst
    warnings: JSONArray | None = None
