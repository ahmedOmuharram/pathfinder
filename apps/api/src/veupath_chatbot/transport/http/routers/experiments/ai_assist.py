"""AI assistant SSE streaming endpoint for the experiment wizard."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.transport.http.schemas.experiments import AiAssistRequest

router = APIRouter()
logger = get_logger(__name__)


@router.post(
    "/ai-assist",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "SSE stream of AI assistant response",
            "content": {"text/event-stream": {"schema": {"type": "string"}}},
        }
    },
)
async def ai_assist(request: AiAssistRequest) -> StreamingResponse:
    """AI assistant for the experiment wizard.

    Streams a response with tool-use activity (web/literature search, site
    catalog lookup, gene lookup) to help the user with the current wizard step.
    """
    from veupath_chatbot.services.experiment.assistant import run_assistant

    history_raw = request.history if isinstance(request.history, list) else []
    history: list[JSONObject] = [h for h in history_raw if isinstance(h, dict)]

    async def _generate() -> AsyncIterator[str]:
        saw_end = False
        try:
            async for event in run_assistant(
                site_id=request.site_id,
                step=request.step,
                message=request.message,
                context=request.context,
                history=history,
                model_override=request.model,
            ):
                event_type = event.get("type", "message")
                if event_type == "message_end":
                    saw_end = True
                yield f"event: {event_type}\ndata: {json.dumps(event.get('data', {}))}\n\n"
        except Exception as exc:
            logger.error("AI assist failed", error=str(exc), exc_info=True)
            yield f"event: error\ndata: {json.dumps({'error': str(exc)})}\n\n"
        if not saw_end:
            yield f"event: message_end\ndata: {json.dumps({})}\n\n"

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
