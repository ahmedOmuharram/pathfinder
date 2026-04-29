from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select

from pathfinder.ai.conversation.event_stream import (
    fetch_snapshot_chunks,
    iter_sse,
    latest_event,
)
from pathfinder.ai.conversation.vercel_adapter import VERCEL_AI_DSP_HEADERS
from pathfinder.persistence.models import BackgroundTask
from pathfinder.persistence.repositories import ConversationRepository
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.transport.http.deps import CurrentUser, DBSession

router = APIRouter(prefix="/api/v1/conversations", tags=["conversations"])

_ACTIVE_TASK_STATUSES: frozenset[str] = frozenset(
    {"pending", "running", "resuming"},
)


class EventsSnapshotResponse(CamelModel):
    chunks: list[dict[str, Any]]
    cursor: int


@router.get(
    "/{conversation_id}/events",
    summary=(
        "SSE: tail live turn chunks plus any post-resume continuation "
        "from a suspended durable task. 204 only when nothing is in flight."
    ),
)
async def conversation_events(
    conversation_id: UUID,
    session: DBSession,
    user_id: CurrentUser,
    after: int = Query(default=0, ge=0),
) -> Response:
    conv = await ConversationRepository(session).get_by_id(conversation_id)
    if conv is None or conv.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="conversation not found",
        )
    tip = await latest_event(conversation_id)
    turn_in_flight = tip is not None and tip[1].get("type") != "done"
    if not turn_in_flight:
        # The latest written chunk is a turn terminator — but a durable
        # task may still be running on the worker; its resume will write
        # NEW chunks (start/.../done) into the chat stream. Returning 204
        # here would make the AI SDK give up and the user would never see
        # the post-resume assistant message. Tail in that case.
        has_active_task = await session.scalar(
            select(BackgroundTask.id)
            .where(
                BackgroundTask.conversation_id == conversation_id,
                BackgroundTask.user_id == user_id,
                BackgroundTask.status.in_(_ACTIVE_TASK_STATUSES),
            )
            .limit(1),
        )
        if has_active_task is None:
            return Response(status_code=status.HTTP_204_NO_CONTENT)
    return StreamingResponse(
        iter_sse(conversation_id=conversation_id, after=after),
        media_type="text/event-stream",
        headers=dict(VERCEL_AI_DSP_HEADERS),
    )


@router.get(
    "/{conversation_id}/events/snapshot",
    response_model=EventsSnapshotResponse,
)
async def conversation_events_snapshot(
    conversation_id: UUID,
    session: DBSession,
    user_id: CurrentUser,
) -> EventsSnapshotResponse:
    conv = await ConversationRepository(session).get_by_id(conversation_id)
    if conv is None or conv.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="conversation not found",
        )
    cursor, chunks = await fetch_snapshot_chunks(conversation_id)
    return EventsSnapshotResponse(chunks=chunks, cursor=cursor)
