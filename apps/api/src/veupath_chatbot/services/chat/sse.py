"""SSE encoding helpers."""

from __future__ import annotations

import json
from typing import Any


def sse_event(event_type: str, data: dict[str, Any]) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


def sse_message_start(
    *,
    auth_token: str,
    strategy_id: str | None = None,
    strategy: dict[str, Any] | None = None,
    plan_session_id: str | None = None,
    plan_session: dict[str, Any] | None = None,
) -> str:
    data: dict[str, Any] = {"authToken": auth_token}
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

