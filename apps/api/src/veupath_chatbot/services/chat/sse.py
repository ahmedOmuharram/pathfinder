"""SSE encoding helpers."""

from __future__ import annotations

import json

from veupath_chatbot.platform.types import JSONObject


def sse_event(event_type: str, data: JSONObject) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


def sse_message_start(
    *,
    strategy_id: str | None = None,
    strategy: JSONObject | None = None,
) -> str:
    data: JSONObject = {}
    if strategy_id is not None:
        data["strategyId"] = strategy_id
    if strategy is not None:
        data["strategy"] = strategy
    return sse_event("message_start", data)


def sse_error(error: str) -> str:
    return sse_event("error", {"error": error})
