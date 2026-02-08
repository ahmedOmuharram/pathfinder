"""SSE encoding helpers."""

from __future__ import annotations

import json

from veupath_chatbot.platform.types import JSONObject


def sse_event(event_type: str, data: JSONObject) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


def sse_message_start(
    *,
    auth_token: str,
    strategy_id: str | None = None,
    strategy: JSONObject | None = None,
    plan_session_id: str | None = None,
    plan_session: JSONObject | None = None,
) -> str:
    data: JSONObject = {"authToken": auth_token}
    if strategy_id is not None:
        data["strategyId"] = strategy_id
    if strategy is not None:
        data["strategy"] = strategy
    if plan_session_id is not None:
        data["planSessionId"] = plan_session_id
    if plan_session is not None:
        data["planSession"] = plan_session
    return sse_event("message_start", data)


def sse_error(error: str) -> str:
    return sse_event("error", {"error": error})
