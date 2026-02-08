"""Strategy counts endpoints (WDK-backed)."""

from __future__ import annotations

from fastapi import APIRouter

from veupath_chatbot.platform.errors import WDKError
from veupath_chatbot.services.strategies.plan_validation import validate_plan_or_raise
from veupath_chatbot.services.strategies.wdk_counts import compute_step_counts_for_plan
from veupath_chatbot.transport.http.deps import CurrentUser
from veupath_chatbot.transport.http.schemas import StepCountsRequest, StepCountsResponse

router = APIRouter(prefix="/api/v1/strategies", tags=["strategies"])


@router.post("/step-counts", response_model=StepCountsResponse)
async def compute_step_counts(
    request: StepCountsRequest,
    user_id: CurrentUser,
) -> StepCountsResponse:
    """Compute step counts by executing the plan in WDK."""
    del user_id  # reserved for future authz
    plan = request.plan.model_dump(exclude_none=True)
    strategy_ast = validate_plan_or_raise(plan)

    try:
        counts = await compute_step_counts_for_plan(plan, strategy_ast, request.site_id)
    except Exception as e:
        raise WDKError(f"WDK compile failed: {e}") from e

    return StepCountsResponse(counts=counts)
