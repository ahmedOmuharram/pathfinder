"""Plan normalization endpoints (frontend-consumer alignment)."""

from __future__ import annotations

from fastapi import APIRouter

from veupath_chatbot.integrations.veupathdb.factory import get_strategy_api
from veupath_chatbot.services.strategies.plan_normalize import canonicalize_plan_parameters
from veupath_chatbot.transport.http.schemas import PlanNormalizeRequest, PlanNormalizeResponse

router = APIRouter(prefix="/api/v1/strategies", tags=["strategies"])


@router.post("/plan/normalize", response_model=PlanNormalizeResponse)
async def normalize_plan(payload: PlanNormalizeRequest) -> PlanNormalizeResponse:
    """Normalize/coerce plan parameters using backend-owned rules.

    This endpoint exists so the frontend can be a consumer of backend canonicalization
    (and avoid re-implementing CSV/JSON parsing and WDK quirks).
    """
    api = get_strategy_api(payload.siteId)
    plan = payload.plan.model_dump(exclude_none=True)

    async def load_details(record_type: str, name: str):
        return await api.client.get_search_details(record_type, name, expand_params=True)

    canonical = await canonicalize_plan_parameters(
        plan=plan,
        site_id=payload.siteId,
        load_search_details=load_details,
    )
    return PlanNormalizeResponse(plan=canonical)

