from __future__ import annotations

from fastapi import APIRouter, Request
from starlette.responses import Response

from pathfinder.services.chat import pipeline_dispatcher
from pathfinder.transport.http.deps import CurrentUser, DBSession

router = APIRouter(tags=["chat"])


@router.post("/api/v1/chat")
async def chat(
    request: Request,
    session: DBSession,
    user_id: CurrentUser,
) -> Response:
    return await pipeline_dispatcher.dispatch(
        request, session=session, user_id=user_id,
    )
