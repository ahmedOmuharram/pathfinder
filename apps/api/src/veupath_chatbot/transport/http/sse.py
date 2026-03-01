"""Reusable SSE (Server-Sent Events) stream helpers for experiment endpoints.

All experiment SSE generators share a common pattern:
1. Create an asyncio queue for events
2. Launch a background task that produces events via the queue
3. Format each event as SSE text and yield to the client
4. Terminate when a sentinel event type is received

This module extracts that pattern into ``sse_stream()``.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable

from veupath_chatbot.platform.types import JSONObject


async def sse_stream(
    producer: Callable[[Callable[[JSONObject], Awaitable[None]]], Awaitable[None]],
    end_event_types: set[str],
) -> AsyncIterator[str]:
    """Generic SSE event stream driven by an async producer function.

    :param producer: An async callable that receives a ``send(event)`` callback
        and pushes ``{"type": ..., "data": ...}`` dicts into it.  The producer
        MUST push at least one event whose ``"type"`` is in *end_event_types*
        before returning (even on error).
    :param end_event_types: Set of event type strings that signal end-of-stream.
        When the consumer sees one of these, it yields the final SSE frame and
        stops iterating.
    """
    queue: asyncio.Queue[JSONObject] = asyncio.Queue()

    async def _send(event: JSONObject) -> None:
        await queue.put(event)

    task = asyncio.create_task(producer(_send))
    try:
        while True:
            event = await queue.get()
            event_type = event.get("type", "experiment_progress")
            data = event.get("data", {})
            yield f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
            if event_type in end_event_types:
                break
    finally:
        task.cancel()
