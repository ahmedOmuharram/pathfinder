from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic_ai.ui.vercel_ai._event_stream import VERCEL_AI_DSP_HEADERS
from starlette.responses import Response, StreamingResponse

from pathfinder.ai.conversation.event_stream import iter_sse, latest_event
from pathfinder.persistence.repositories import ConversationRepository
from pathfinder.transport.http.deps import CurrentUser, DBSession

router = APIRouter(prefix="/api/v1/conversations", tags=["conversations"])


@router.get(
    "/{conversation_id}/events",
    summary="SSE: tail live turn chunks. 204 when no active stream.",
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
    if tip is None or tip[1].get("type") == "done":
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return StreamingResponse(
        iter_sse(conversation_id=conversation_id, after=after),
        media_type="text/event-stream",
        headers=dict(VERCEL_AI_DSP_HEADERS),
    )
