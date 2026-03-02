"""GET step endpoint."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from veupath_chatbot.platform.errors import ErrorCode, NotFoundError
from veupath_chatbot.services.strategies.serialization import build_steps_data_from_plan
from veupath_chatbot.transport.http.deps import CurrentUser, StrategyRepo
from veupath_chatbot.transport.http.routers._authz import get_owned_strategy_or_404
from veupath_chatbot.transport.http.routers.steps._shared import (
    find_step,
    get_steps_as_objects,
)
from veupath_chatbot.transport.http.schemas import StepResponse

router = APIRouter(prefix="/api/v1/strategies/{strategyId}/steps", tags=["steps"])


@router.get("/{step_id}", response_model=StepResponse)
async def get_step(
    strategyId: UUID,
    step_id: str,
    strategy_repo: StrategyRepo,
    user_id: CurrentUser,
) -> StepResponse:
    """Get a step from a strategy."""
    strategy = await get_owned_strategy_or_404(strategy_repo, strategyId, user_id)
    steps_raw = build_steps_data_from_plan(strategy.plan or {})
    steps = get_steps_as_objects(steps_raw)
    step = find_step(steps, step_id)
    if not step:
        raise NotFoundError(code=ErrorCode.STEP_NOT_FOUND, title="Step not found")
    return StepResponse.model_validate(step)
