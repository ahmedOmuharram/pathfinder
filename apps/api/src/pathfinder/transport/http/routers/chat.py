from __future__ import annotations

from fastapi import APIRouter, Request
from starlette.responses import Response

from pathfinder.ai.chat import dispatcher
from pathfinder.transport.http.deps import CurrentUser, DBSession

router = APIRouter(tags=["chat"])


@router.post("/api/v1/chat")
async def chat(
    request: Request,
    session: DBSession,
    user_id: CurrentUser,
) -> Response:
    return await dispatcher.dispatch(
        request, session=session, user_id=user_id,
    )
