"""Plan normalization endpoints (frontend-consumer alignment)."""

from fastapi import APIRouter

from pathfinder.services.strategies.plan_normalize import (
    canonicalize_plan_parameters,
)
from pathfinder.transport.http.schemas import (
    PlanNormalizeRequest,
    PlanNormalizeResponse,
)

router = APIRouter(prefix="/api/v1/strategies", tags=["strategies"])


@router.post("/plan/normalize", response_model=PlanNormalizeResponse)
async def normalize_plan(payload: PlanNormalizeRequest) -> PlanNormalizeResponse:
    """Normalize/coerce plan parameters using backend-owned rules.

    This endpoint exists so the frontend can be a consumer of backend canonicalization
    (and avoid re-implementing CSV/JSON parsing and WDK quirks).
    """
    canonical = await canonicalize_plan_parameters(
        plan=payload.plan, site_id=payload.siteId,
    )
    return PlanNormalizeResponse(plan=canonical)
