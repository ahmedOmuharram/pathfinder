"""SSE encoding helpers."""

from __future__ import annotations

import json
from typing import Any


def sse_event(event_type: str, data: dict[str, Any]) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


def sse_message_start(*, strategy_id: str, strategy: dict[str, Any], auth_token: str) -> str:
    return sse_event(
        "message_start",
        {"strategyId": strategy_id, "strategy": strategy, "authToken": auth_token},
    )


def sse_error(error: str) -> str:
    return sse_event("error", {"error": error})

