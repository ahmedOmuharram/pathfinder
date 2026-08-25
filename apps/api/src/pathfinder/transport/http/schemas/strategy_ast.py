"""Strategy AST normalize request/response DTOs."""

from assistant_core.platform.pydantic_base import CamelModel
from assistant_core.platform.types import JSONArray

from pathfinder.domain.strategy.strategy_ast import StrategyAst
from pathfinder.transport.http.schemas.site_id import SiteId


class StrategyAstNormalizeRequest(CamelModel):
    site_id: SiteId
    strategy_ast: StrategyAst


class StrategyAstNormalizeResponse(CamelModel):
    strategy_ast: StrategyAst
    warnings: JSONArray | None = None
