from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from pathfinder.ai.conversation.dispatcher import dispatch
from pathfinder.ai.conversation.request_body import ChatRequestBody
from pathfinder.transport.http.deps import (
    DBSession,
    QuotaCheckedUser,
    with_wdk_identity,
)

router = APIRouter(tags=["chat"])


# with_wdk_identity runs before dispatch so the deferred chat_turn job
# captures a durable WDK identity in its payload — the worker then builds
# strategies as the same WDK user the api edits them as.
@router.post("/api/v1/chat", dependencies=[Depends(with_wdk_identity)])
async def chat(
    body: ChatRequestBody,
    session: DBSession,
    user_id: QuotaCheckedUser,
) -> Response:
    return await dispatch(body=body, session=session, user_id=user_id)
