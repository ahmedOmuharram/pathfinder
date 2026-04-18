"""Strategy counts endpoints (WDK-backed)."""

from fastapi import APIRouter

from pathfinder.platform.errors import WDKError
from pathfinder.services.strategies.plan_validation import validate_plan_or_raise
from pathfinder.services.strategies.wdk_counts import compute_step_counts_for_plan
from pathfinder.transport.http.deps import CurrentUser
from pathfinder.transport.http.schemas import StepCountsRequest, StepCountsResponse

router = APIRouter(prefix="/api/v1/conversations", tags=["conversations"])


@router.post("/step-counts", response_model=StepCountsResponse)
async def compute_step_counts(
    request: StepCountsRequest,
    user_id: CurrentUser,
) -> StepCountsResponse:
    """Compute step counts by executing the plan in WDK."""
    del user_id  # reserved for future authz
    plan = request.plan.model_dump(exclude_none=True)
    payload = validate_plan_or_raise(plan)

    try:
        counts = await compute_step_counts_for_plan(payload, request.site_id)
    except Exception as e:
        msg = f"WDK compile failed: {e}"
        raise WDKError(msg) from e

    return StepCountsResponse(counts=counts)
