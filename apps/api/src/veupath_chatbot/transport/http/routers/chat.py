"""Chat endpoint — starts a background chat operation."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from veupath_chatbot.platform.security import limiter
from veupath_chatbot.services.chat.orchestrator import start_chat_stream
from veupath_chatbot.services.chat.types import ChatContext, ChatTurnConfig
from veupath_chatbot.transport.http.deps import (
    CurrentUser,
    StreamRepo,
    UserRepo,
)
from veupath_chatbot.transport.http.schemas import ChatRequest

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
        mentions=body.mentions or None,
        disable_rag=body.disable_rag,
        disabled_tools=body.disabled_tools,
        provider_override=body.provider,
        model_override=body.model_id,
        reasoning_effort=body.reasoning_effort,
        temperature=body.temperature,
        seed=body.seed,
        context_size=body.context_size,
        response_tokens=body.response_tokens,
        reasoning_budget=body.reasoning_budget,
    )
    operation_id, strategy_id = await start_chat_stream(
        message=body.message,
        site_id=body.site_id,
        strategy_id=body.strategy_id,
        context=context,
        config=config,
    )
    return JSONResponse(
        {"operationId": operation_id, "strategyId": strategy_id},
        status_code=202,
    )
