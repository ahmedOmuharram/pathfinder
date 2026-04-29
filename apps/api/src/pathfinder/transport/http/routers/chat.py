from __future__ import annotations

from fastapi import APIRouter, Response

from pathfinder.ai.conversation.dispatcher import dispatch
from pathfinder.ai.conversation.request_body import ChatRequestBody
from pathfinder.transport.http.deps import DBSession, QuotaCheckedUser

router = APIRouter(tags=["chat"])


@router.post("/api/v1/chat")
async def chat(
    body: ChatRequestBody,
    session: DBSession,
    user_id: QuotaCheckedUser,
) -> Response:
    return await dispatch(body=body, session=session, user_id=user_id)
