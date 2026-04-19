"""Strategy AST normalization endpoint (frontend-consumer alignment)."""

from fastapi import APIRouter

from pathfinder.services.strategies.plan_normalize import (
    canonicalize_strategy_ast_parameters,
)
from pathfinder.transport.http.schemas import (
    StrategyAstNormalizeRequest,
    StrategyAstNormalizeResponse,
)

router = APIRouter(prefix="/api/v1/conversations", tags=["conversations"])


@router.post(
    "/strategy-ast/normalize", response_model=StrategyAstNormalizeResponse,
)
async def normalize_strategy_ast(
    payload: StrategyAstNormalizeRequest,
) -> StrategyAstNormalizeResponse:
    """Normalize/coerce strategy AST parameters using backend-owned rules.

    This endpoint exists so the frontend can be a consumer of backend
    canonicalization (and avoid re-implementing CSV/JSON parsing and WDK
    quirks).
    """
    canonical = await canonicalize_strategy_ast_parameters(
        strategy_ast=payload.strategy_ast, site_id=payload.site_id,
    )
    return StrategyAstNormalizeResponse(strategy_ast=canonical)
