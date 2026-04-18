from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from pathfinder.services.checkpoints import (
    CheckpointNode,
    CheckpointService,
    CheckpointSnapshot,
)
from pathfinder.transport.http.deps import (
    CurrentUser,
    get_checkpoint_service,
)
from pathfinder.transport.http.schemas.checkpoints import (
    ForkRequest,
    ForkResponse,
)

router = APIRouter(prefix="/api/v1/conversations", tags=["checkpoints"])

CheckpointSvc = Annotated[CheckpointService, Depends(get_checkpoint_service)]


@router.get("/{conversation_id}/checkpoints", response_model=list[CheckpointNode])
async def list_checkpoints(
    conversation_id: UUID,
    user_id: CurrentUser,
    svc: CheckpointSvc,
) -> list[CheckpointNode]:
    """Return the full checkpoint tree for a chat thread.

    Joins the per-user labels sidecar via the authenticated user — labels
    on other users' rows are intentionally invisible.
    """
    return await svc.list_tree(thread_id=str(conversation_id), user_id=user_id)


@router.get(
    "/{conversation_id}/checkpoints/{checkpoint_id}",
    response_model=CheckpointSnapshot,
)
async def get_checkpoint(
    conversation_id: UUID,
    checkpoint_id: str,
    svc: CheckpointSvc,
) -> CheckpointSnapshot:
    """Materialize a single checkpoint via ``graph.aget_state``."""
    snap = await svc.get_snapshot(
        thread_id=str(conversation_id), checkpoint_id=checkpoint_id
    )
    if not snap.values and not snap.next and not snap.metadata:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="checkpoint not found",
        )
    return snap


@router.post(
    "/{conversation_id}/fork",
    response_model=ForkResponse,
    status_code=status.HTTP_201_CREATED,
)
async def fork_checkpoint(
    conversation_id: UUID,
    body: ForkRequest,
    svc: CheckpointSvc,
) -> ForkResponse:
    """Create a branched checkpoint via ``graph.aupdate_state``."""
    new_id = await svc.fork(
        thread_id=str(conversation_id),
        from_checkpoint_id=body.from_checkpoint_id,
        state_override=body.state_override,
        as_node=body.as_node,
    )
    return ForkResponse(new_checkpoint_id=new_id)
