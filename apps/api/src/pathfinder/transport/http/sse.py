"""Reusable SSE (Server-Sent Events) stream helpers for experiment endpoints.

All experiment SSE generators share a common pattern:
1. Create an asyncio queue for events
2. Launch a background task that produces events via the queue
3. Yield ``ServerSentEvent`` objects to ``EventSourceResponse``
4. Terminate when a sentinel event type is received

This module extracts that pattern into ``sse_stream()``.
"""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable

from fastapi.sse import ServerSentEvent

from pathfinder.platform.errors import sanitize_error_for_client
from pathfinder.platform.logging import get_logger
from pathfinder.platform.types import JSONObject

logger = get_logger(__name__)

# Sentinel pushed to the queue when the producer crashes so the consumer
# never blocks indefinitely on ``queue.get()``.
_INTERNAL_ERROR_EVENT_TYPE = "internal_error"


def _sse_event_from_dict(event: JSONObject) -> ServerSentEvent:
    """Build a ``ServerSentEvent`` from a ``{"type": ..., "data": ...}`` dict."""
    event_type = event.get("type", "experiment_progress")
    data = event.get("data", {})
    return ServerSentEvent(data=data, event=str(event_type))


async def sse_stream(
    producer: Callable[[Callable[[JSONObject], Awaitable[None]]], Awaitable[None]],
    end_event_types: set[str],
) -> AsyncIterator[ServerSentEvent]:
    """Generic SSE event stream driven by an async producer function.

    :param producer: An async callable that receives a ``send(event)`` callback
        and pushes ``{"type": ..., "data": ...}`` dicts into it.
    :param end_event_types: Set of event type strings that signal end-of-stream.
        When the consumer sees one of these, it yields the final SSE event and
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
            yield _sse_event_from_dict(event)
            event_type = event.get("type", "experiment_progress")
            if event_type in terminal_types:
                break
    finally:
        task.cancel()
