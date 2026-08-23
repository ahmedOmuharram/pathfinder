from __future__ import annotations

from uuid import UUID

from assistant_core.platform.pydantic_base import CamelModel
from fastapi import APIRouter, HTTPException, status

from pathfinder.services.conversations.revert import (
    RevertError,
    revert_conversation_to_message,
)
from pathfinder.transport.http.deps import CurrentUser, DBSession

router = APIRouter(prefix="/api/v1/conversations", tags=["conversations"])


class RevertRequest(CamelModel):
    message_id: UUID


@router.post(
    "/{conversation_id}/revert-to-message",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete all state at or after the target user message.",
)
async def revert_to_message(
    conversation_id: UUID,
    request: RevertRequest,
    session: DBSession,
    user_id: CurrentUser,
) -> None:
    try:
        await revert_conversation_to_message(
            session,
            conversation_id=conversation_id,
            target_message_id=request.message_id,
            user_id=user_id,
        )
    except RevertError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await session.commit()
