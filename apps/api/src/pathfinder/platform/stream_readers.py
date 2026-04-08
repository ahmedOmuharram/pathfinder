"""Public stream-reading functions: chat history and in-progress thinking.

These coroutines drive Redis I/O (``XRANGE``) and delegate per-event
processing to the reconstruction engine in ``platform.reconstruction``.
"""

import json

from redis.asyncio import Redis

from pathfinder.platform.event_schemas import (
    ToolCallEndEventData,
    ToolCallStartEventData,
)
from pathfinder.platform.reconstruction import (
    _process_stream_event,
    _TurnAccumulator,
)
from pathfinder.platform.types import JSONObject


async def read_stream_messages(redis: Redis, stream_id: str) -> list[JSONObject]:
    """Read all user + assistant messages from a Redis stream.

    Aggregates metadata from surrounding events (tool_call_start/end,
    citations, planning_artifact, reasoning) into each assistant_message
    so the full conversation context survives refresh.

    Used by the GET /strategies/{id} endpoint to return chat history.
    """
    entries = await redis.xrange(f"stream:{stream_id}")
    messages: list[JSONObject] = []
    turn = _TurnAccumulator()

    for entry_id, fields in entries:
        event_type = fields.get(b"type", b"").decode()
        try:
            data = json.loads(fields[b"data"])
        except json.JSONDecodeError, KeyError:
            continue

        _process_stream_event(event_type, data, entry_id, turn, messages)

    return messages


def _collect_open_tool_calls(
    entries: list[tuple[bytes | str, dict[bytes, bytes]]],
    start_idx: int,
) -> dict[str, JSONObject]:
    """Collect tool calls that have started but not ended since *start_idx*."""
    open_tools: dict[str, JSONObject] = {}
    for _eid, fields in entries[start_idx:]:
        event_type = fields.get(b"type", b"").decode()
        if event_type == "tool_call_start":
            try:
                data = json.loads(fields[b"data"])
                start = ToolCallStartEventData.model_validate(data)
                open_tools[start.id] = {
                    "id": start.id,
                    "name": start.name,
                    "arguments": start.arguments,
                }
            except json.JSONDecodeError, KeyError, ValueError:
                pass
        elif event_type == "tool_call_end":
            try:
                data = json.loads(fields[b"data"])
                end = ToolCallEndEventData.model_validate(data)
                open_tools.pop(end.id, None)
            except json.JSONDecodeError, KeyError, ValueError:
                pass
    return open_tools


async def read_stream_thinking(redis: Redis, stream_id: str) -> JSONObject | None:
    """Derive in-progress thinking state from stream events.

    Thinking = tool_call_start events without matching tool_call_end,
    from the most recent active operation.
    """
    entries = await redis.xrange(f"stream:{stream_id}")

    # Find the last message_start (marks beginning of a turn)
    last_start_idx = -1
    for i, (_eid, fields) in enumerate(entries):
        if fields.get(b"type", b"") == b"message_start":
            last_start_idx = i

    if last_start_idx < 0:
        return None

    # Check if this turn is still active (no message_end after last start)
    has_end = any(
        fields.get(b"type", b"") == b"message_end"
        for _eid, fields in entries[last_start_idx:]
    )
    if has_end:
        return None

    open_tools = _collect_open_tool_calls(entries, last_start_idx)
    if not open_tools:
        return None

    return {
        "toolCalls": list(open_tools.values()),
    }
