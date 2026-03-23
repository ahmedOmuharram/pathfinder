"""Plan normalization endpoints (frontend-consumer alignment)."""

from collections.abc import Mapping

from fastapi import APIRouter

from veupath_chatbot.domain.strategy.ast import StrategyAST
from veupath_chatbot.platform.errors import WDKError
from veupath_chatbot.platform.types import JSONObject, JSONValue
from veupath_chatbot.services.strategies.plan_normalize import (
    canonicalize_plan_parameters,
)
from veupath_chatbot.services.wdk import (
    encode_context_param_values_for_wdk,
    get_strategy_api,
)
from veupath_chatbot.transport.http.schemas import (
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
    api = get_strategy_api(payload.siteId)
    plan: JSONObject = payload.plan.model_dump(by_alias=True, exclude_none=True)

    async def load_details(
        record_type: str, name: str, params: Mapping[str, JSONValue]
    ) -> JSONObject:
        # Use context-dependent search details so vocab-dependent params (e.g. min/max/avg ops)
        # validate correctly when the plan already contains concrete selections.
        # Convert params to JSONObject for encode_context_param_values_for_wdk
        params_dict: JSONObject = dict(params) if isinstance(params, Mapping) else {}
        context = encode_context_param_values_for_wdk(params_dict)
        try:
            result = await api.client.get_search_details_with_params(
                record_type,
                name,
                context=context,
                expand_params=True,
            )
        except WDKError:
            # Some WDK deployments/questions error on POST /searches/{name} when certain context
            # values are provided (500 Internal Error). Fall back to GET details so we can still
            # canonicalize plan shapes without blocking the user.
            result = await api.client.get_search_details(
                record_type,
                name,
                expand_params=True,
            )
        return result if isinstance(result, dict) else {}

    canonical = await canonicalize_plan_parameters(
        plan=plan,
        site_id=payload.siteId,
        load_search_details=load_details,
    )
    canonical_plan = StrategyAST.model_validate(canonical)
    return PlanNormalizeResponse(plan=canonical_plan)
