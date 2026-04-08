"""SSE event helpers for workbench chat streaming.

Converts pydantic-ai tool call/result objects into SSE-shaped dicts
that the Redis emit layer can publish to clients.
"""

import json
from typing import cast

from pydantic_ai.messages import ToolCallPart

from pathfinder.platform.event_schemas import (
    ToolCallStartEventData,
)
from pathfinder.platform.types import JSONObject


def parse_tool_call_args(args: str | dict[str, object] | None) -> JSONObject:
    """Normalize ToolCallPart.args to a dict."""
    if isinstance(args, dict):
        return cast("JSONObject", dict(args))
    if isinstance(args, str):
        try:
            parsed = json.loads(args)
        except (json.JSONDecodeError, ValueError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def tool_call_start_event(part: ToolCallPart) -> JSONObject:
    """Build a tool_call_start SSE event from a ToolCallPart."""
    return {
        "type": "tool_call_start",
        "data": ToolCallStartEventData(
            id=part.tool_call_id,
            name=part.tool_name,
            arguments=parse_tool_call_args(part.args),
        ).model_dump(by_alias=True),
    }


def serialize_tool_content(content: object) -> str:
    """Serialize tool result content to a string."""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        return json.dumps(content)
    return str(content)
