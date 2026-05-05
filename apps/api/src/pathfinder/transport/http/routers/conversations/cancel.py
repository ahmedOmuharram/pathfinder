from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import select

from pathfinder.persistence.models import ConversationEvent
from pathfinder.persistence.repositories import (
    ChatTurnCancellationRepository,
    ConversationRepository,
)
from pathfinder.persistence.session import async_session_factory
from pathfinder.transport.http.deps import CurrentUser, DBSession

router = APIRouter(prefix="/api/v1/conversations", tags=["conversations"])


@router.post(
    "/{conversation_id}/turns/{turn_id}/cancel",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def cancel_turn(
    conversation_id: UUID,
    turn_id: UUID,
    session: DBSession,
    user_id: CurrentUser,
) -> Response:
    conv = await ConversationRepository(session).get_by_id(conversation_id)
    if conv is None or conv.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="conversation not found",
        )
    repo = ChatTurnCancellationRepository(session_factory=async_session_factory)
    await repo.request_cancel(
        conversation_id=conversation_id, turn_id=turn_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{conversation_id}/cancel",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def cancel_conversation(
    conversation_id: UUID,
    session: DBSession,
    user_id: CurrentUser,
) -> Response:
    conv = await ConversationRepository(session).get_by_id(conversation_id)
    if conv is None or conv.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="conversation not found",
        )
    row = await session.scalar(
        select(ConversationEvent)
        .where(
            ConversationEvent.conversation_id == conversation_id,
            ConversationEvent.task_id.is_(None),
        )
        .order_by(ConversationEvent.id.desc())
        .limit(1),
    )
    if row is None or row.chunk.get("type") == "done" or row.turn_id is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    repo = ChatTurnCancellationRepository(session_factory=async_session_factory)
    await repo.request_cancel(
        conversation_id=conversation_id, turn_id=row.turn_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
