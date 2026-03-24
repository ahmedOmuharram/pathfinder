"""Reusable SSE (Server-Sent Events) stream helpers for experiment endpoints.

All experiment SSE generators share a common pattern:
1. Create an asyncio queue for events
2. Launch a background task that produces events via the queue
3. Format each event as SSE text and yield to the client
4. Terminate when a sentinel event type is received

This module extracts that pattern into ``sse_stream()``.
"""

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable

from veupath_chatbot.platform.errors import sanitize_error_for_client
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject

logger = get_logger(__name__)

SSE_HEADERS: dict[str, str] = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}

# Sentinel pushed to the queue when the producer crashes so the consumer
# never blocks indefinitely on ``queue.get()``.
_INTERNAL_ERROR_EVENT_TYPE = "internal_error"


def _format_sse_frame(event: JSONObject) -> str:
    """Format a single event dict as an SSE text frame."""
    event_type = event.get("type", "experiment_progress")
    data = event.get("data", {})
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


async def sse_stream(
    producer: Callable[[Callable[[JSONObject], Awaitable[None]]], Awaitable[None]],
    end_event_types: set[str],
) -> AsyncIterator[str]:
    """Generic SSE event stream driven by an async producer function.

    :param producer: An async callable that receives a ``send(event)`` callback
        and pushes ``{"type": ..., "data": ...}`` dicts into it.
    :param end_event_types: Set of event type strings that signal end-of-stream.
        When the consumer sees one of these, it yields the final SSE frame and
        stops iterating.

    If the producer raises without sending an end event, an ``internal_error``
    event is injected automatically so the consumer never hangs.
    """
    queue: asyncio.Queue[JSONObject] = asyncio.Queue()
    terminal_types = end_event_types | {_INTERNAL_ERROR_EVENT_TYPE}

    async def _send(event: JSONObject) -> None:
        await queue.put(event)

    async def _guarded_producer() -> None:
        try:
            await producer(_send)
        except Exception as exc:
            logger.exception("SSE producer crashed")
            await queue.put(
                {
                    "type": _INTERNAL_ERROR_EVENT_TYPE,
                    "data": {"error": sanitize_error_for_client(exc)},
                }
            )

    task = asyncio.create_task(_guarded_producer())
    try:
        while True:
            event = await queue.get()
            frame = _format_sse_frame(event)
            yield frame
            event_type = event.get("type", "experiment_progress")
            if event_type in terminal_types:
                break
    finally:
        task.cancel()
