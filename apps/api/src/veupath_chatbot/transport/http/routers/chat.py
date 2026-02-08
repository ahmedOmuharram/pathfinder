"""Chat endpoints with SSE streaming."""

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from veupath_chatbot.services.chat.orchestrator import start_chat_stream
from veupath_chatbot.transport.http.deps import (
    OptionalUser,
    PlanSessionRepo,
    StrategyRepo,
    UserRepo,
)
from veupath_chatbot.transport.http.schemas import ChatRequest

router = APIRouter(prefix="/api/v1", tags=["chat"])


@router.post(
    "/chat",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "Successful Response",
            "content": {
                "text/event-stream": {"schema": {"type": "string"}},
            },
        }
    },
)
async def chat(
    request: ChatRequest,
    user_repo: UserRepo,
    strategy_repo: StrategyRepo,
    plan_repo: PlanSessionRepo,
    user_id: OptionalUser,
) -> StreamingResponse:
    """Send a chat message and receive streaming response.

    Returns a Server-Sent Events stream with response chunks.
    """
    auth_token, sse_iter = await start_chat_stream(
        message=request.message,
        site_id=request.site_id,
        strategy_id=request.strategy_id,
        plan_session_id=request.plan_session_id,
        mode=request.mode,
        user_id=user_id,
        user_repo=user_repo,
        strategy_repo=strategy_repo,
        plan_repo=plan_repo,
    )
    response = StreamingResponse(
        sse_iter,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
    response.set_cookie(
        key="pathfinder-auth",
        value=auth_token,
        httponly=True,
        samesite="lax",
    )
    return response
