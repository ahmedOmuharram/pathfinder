"""Plan normalization endpoints (frontend-consumer alignment)."""

from __future__ import annotations

from fastapi import APIRouter

from veupath_chatbot.integrations.veupathdb.client import encode_context_param_values_for_wdk
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

    async def load_details(record_type: str, name: str, params: dict[str, object]):
        # Use context-dependent search details so vocab-dependent params (e.g. min/max/avg ops)
        # validate correctly when the plan already contains concrete selections.
        context = encode_context_param_values_for_wdk(params or {})
        return await api.client.get_search_details_with_params(
            record_type,
            name,
            context=context,
            expand_params=True,
        )

    canonical = await canonicalize_plan_parameters(
        plan=plan,
        site_id=payload.siteId,
        load_search_details=load_details,
    )
    return PlanNormalizeResponse(plan=canonical)

