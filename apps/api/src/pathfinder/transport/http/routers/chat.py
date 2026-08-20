from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from pathfinder.ai.conversation.dispatcher import dispatch
from pathfinder.ai.conversation.request_body import ChatRequestBody
from pathfinder.transport.http.deps import (
    DBSession,
    QuotaCheckedUser,
    require_registered_wdk_identity,
)

router = APIRouter(tags=["chat"])


# The gate runs before dispatch, so the deferred chat_turn job carries the
# user's own registered token and the worker builds strategies as that user.
@router.post("/api/v1/chat", dependencies=[Depends(require_registered_wdk_identity)])
async def chat(
    body: ChatRequestBody,
    session: DBSession,
    user_id: QuotaCheckedUser,
) -> Response:
    return await dispatch(body=body, session=session, user_id=user_id)
