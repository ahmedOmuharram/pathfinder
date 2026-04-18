from __future__ import annotations

from fastapi import APIRouter, Request
from starlette.responses import Response

from pathfinder.ai.conversation.dispatcher import ChatRequestBody, dispatch
from pathfinder.transport.http.deps import CurrentUser, DBSession

router = APIRouter(tags=["chat"])


@router.post("/api/v1/chat")
async def chat(
    body: ChatRequestBody,
    request: Request,
    session: DBSession,
    user_id: CurrentUser,
) -> Response:
    return await dispatch(
        body=body,
        session=session,
        user_id=user_id,
        compiled_graph=request.app.state.compiled_graph,
        memory_store=request.app.state.memory_store,
    )
