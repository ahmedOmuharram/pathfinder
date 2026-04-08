"""Chat endpoint — starts a background chat operation."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from pathfinder.platform.security import limiter
from pathfinder.services.chat.orchestrator import start_chat_stream
from pathfinder.services.chat.types import ChatContext, ChatTurnConfig
from pathfinder.transport.http.deps import (
    CurrentUser,
    StreamRepo,
    UserRepo,
)
from pathfinder.transport.http.schemas import ChatRequest

router = APIRouter(prefix="/api/v1", tags=["chat"])


@router.post("/chat", status_code=202)
@limiter.limit("30/minute")
async def chat(
    request: Request,
    body: ChatRequest,
    user_repo: UserRepo,
    stream_repo: StreamRepo,
    user_id: CurrentUser,
) -> JSONResponse:
    """Start a chat operation and return its operation ID.

    The client subscribes to GET /operations/{operationId}/subscribe for SSE events.
    """
    context = ChatContext(
        user_id=user_id,
        user_repo=user_repo,
        stream_repo=stream_repo,
    )
    config = ChatTurnConfig(
        pipeline=body.pipeline,
        mentions=body.mentions or None,
        disable_rag=body.disable_rag,
        temperature=body.temperature,
        seed=body.seed,
    )
    operation_id, strategy_id, entry_id = await start_chat_stream(
        message=body.message,
        site_id=body.site_id,
        strategy_id=body.strategy_id,
        context=context,
        config=config,
    )
    return JSONResponse(
        {"operationId": operation_id, "strategyId": strategy_id, "entryId": entry_id},
        status_code=202,
    )
