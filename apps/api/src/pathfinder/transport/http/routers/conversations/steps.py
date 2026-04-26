from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from pathfinder.services.strategies.schemas import StepResponse
from pathfinder.services.strategies.step_patch import apply_step_patch
from pathfinder.transport.http.deps import ConversationRepo, CurrentUser
from pathfinder.transport.http.routers._authz import get_owned_conversation_or_404
from pathfinder.transport.http.schemas import StepPatchRequest

router = APIRouter(prefix="/api/v1/conversations", tags=["conversations"])


@router.patch(
    "/{strategyId:uuid}/steps/{stepId}",
    response_model=StepResponse,
)
async def patch_step(
    strategyId: UUID,
    stepId: str,
    request: StepPatchRequest,
    site_id: Annotated[str, Query(alias="siteId")],
    conv_repo: ConversationRepo,
    user_id: CurrentUser,
) -> StepResponse:
    await get_owned_conversation_or_404(conv_repo, strategyId, user_id)
    return await apply_step_patch(
        conv_repo=conv_repo,
        strategy_id=strategyId,
        step_id=stepId,
        site_id=site_id,
        patch=request,
    )
