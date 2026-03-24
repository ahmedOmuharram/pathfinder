"""Extended event system tests — edge cases for event parsing and projection.

Focuses on:
- _parse_arguments edge cases (non-dict JSON, numbers, arrays, nested)
- _entry_id_to_iso edge cases (invalid entry IDs, boundary timestamps)
- read_stream_messages with malformed event data
- read_stream_thinking with edge cases
- Projection skipping for non-projected event types
- emit edge cases with real Redis
"""

import json
from datetime import UTC, datetime
from uuid import uuid4

from redis.asyncio import Redis

from veupath_chatbot.platform.events import (
    _entry_id_to_iso,
    emit,
    read_stream_messages,
    read_stream_thinking,
)
from veupath_chatbot.platform.redis import get_redis

# ---------------------------------------------------------------------------
# Helpers — write raw events to a real Redis stream
# ---------------------------------------------------------------------------


async def _xadd(
    redis: Redis,
    stream_key: str,
    event_type: str,
    data: object,
    *,
    operation_id: str = "op_1",
) -> bytes:
    """Write a raw event entry to a Redis stream."""
    return await redis.xadd(
        stream_key,
        {
            "op": operation_id.encode(),
            "type": event_type.encode(),
            "data": json.dumps(data, default=str).encode()
            if not isinstance(data, bytes)
            else data,
        },
    )


async def _xadd_raw(
    redis: Redis,
    stream_key: str,
    fields: dict[bytes, bytes],
) -> bytes:
    """Write raw bytes fields to a Redis stream (for malformed data tests)."""
    return await redis.xadd(stream_key, fields)


class TestEntryIdToIso:
    """_entry_id_to_iso converts Redis entry IDs to ISO 8601 timestamps."""

    def test_valid_entry_id(self) -> None:
        # 1709234567890 ms = some specific datetime
        result = _entry_id_to_iso("1709234567890-0")
        assert result.endswith(("+00:00", "Z"))
        # Should parse as a valid ISO 8601 datetime
        dt = datetime.fromisoformat(result)
        assert dt.tzinfo is not None

    def test_bytes_entry_id(self) -> None:
        result = _entry_id_to_iso(b"1709234567890-0")
        dt = datetime.fromisoformat(result)
        assert dt.tzinfo is not None

    def test_invalid_entry_id_returns_now(self) -> None:
        """Non-numeric entry ID should fall back to current time."""
        result = _entry_id_to_iso("invalid-entry-id")
        dt = datetime.fromisoformat(result)
        # Should be approximately now
        diff = abs((datetime.now(UTC) - dt).total_seconds())
        assert diff < 5

    def test_zero_timestamp(self) -> None:
        result = _entry_id_to_iso("0-0")
        dt = datetime.fromisoformat(result)
        # Unix epoch
        assert dt.year == 1970

    def test_entry_id_without_sequence(self) -> None:
        """Entry ID with no '-N' suffix — split('-')[0] still works."""
        result = _entry_id_to_iso("1709234567890")
        dt = datetime.fromisoformat(result)
        assert dt.tzinfo is not None


class TestReadStreamMessagesEdgeCases:
    """Edge cases for read_stream_messages — using real Redis."""

    async def test_empty_stream(self) -> None:
        redis = get_redis()
        messages = await read_stream_messages(redis, str(uuid4()))
        assert messages == []

    async def test_malformed_data_skipped(self) -> None:
        """Events with invalid JSON data should be skipped without crashing."""
        redis = get_redis()
        stream_id = str(uuid4())
        stream_key = f"stream:{stream_id}"

        # Write a malformed event (invalid JSON)
        await _xadd_raw(
            redis,
            stream_key,
            {
                b"op": b"op_1",
                b"type": b"user_message",
                b"data": b"not valid json {{{",
            },
        )
        # Write a valid assistant_message
        await _xadd(
            redis,
            stream_key,
            "assistant_message",
            {"messageId": "m1", "content": "hello"},
        )

        messages = await read_stream_messages(redis, stream_id)
        # The malformed user_message is skipped; only assistant_message remains
        assert len(messages) == 1
        assert messages[0]["role"] == "assistant"

    async def test_missing_data_field_skipped(self) -> None:
        """Events without a b'data' key should be skipped."""
        redis = get_redis()
        stream_id = str(uuid4())
        stream_key = f"stream:{stream_id}"

        # Write an event without a data field
        await _xadd_raw(
            redis,
            stream_key,
            {
                b"op": b"op_1",
                b"type": b"user_message",
                # no b"data" key
            },
        )
        # Write a valid event
        await _xadd(
            redis,
            stream_key,
            "assistant_message",
            {"content": "hi"},
        )

        messages = await read_stream_messages(redis, stream_id)
        assert len(messages) == 1
        assert messages[0]["role"] == "assistant"

    async def test_assistant_message_with_empty_content(self) -> None:
        redis = get_redis()
        stream_id = str(uuid4())
        stream_key = f"stream:{stream_id}"

        await _xadd(
            redis,
            stream_key,
            "assistant_message",
            {"messageId": "m1"},
        )

        messages = await read_stream_messages(redis, stream_id)
        assert len(messages) == 1
        assert messages[0]["content"] == ""

    async def test_planning_artifacts_aggregated(self) -> None:
        redis = get_redis()
        stream_id = str(uuid4())
        stream_key = f"stream:{stream_id}"

        await _xadd(redis, stream_key, "message_start", {})
        await _xadd(
            redis,
            stream_key,
            "planning_artifact",
            {"planningArtifact": {"type": "plan", "steps": [1, 2]}},
        )
        await _xadd(
            redis,
            stream_key,
            "assistant_message",
            {"messageId": "m1", "content": "done"},
        )
        await _xadd(redis, stream_key, "message_end", {})

        messages = await read_stream_messages(redis, stream_id)
        assert len(messages) == 1
        assert "planningArtifacts" in messages[0]
        assert len(messages[0]["planningArtifacts"]) == 1

    async def test_turn_reset_on_message_end(self) -> None:
        """Turn accumulators should reset after message_end."""
        redis = get_redis()
        stream_id = str(uuid4())
        stream_key = f"stream:{stream_id}"

        # Turn 1
        await _xadd(redis, stream_key, "message_start", {}, operation_id="op_1")
        await _xadd(
            redis,
            stream_key,
            "tool_call_start",
            {"id": "tc1", "name": "tool_a"},
            operation_id="op_1",
        )
        await _xadd(
            redis,
            stream_key,
            "assistant_message",
            {"messageId": "m1", "content": "turn1"},
            operation_id="op_1",
        )
        await _xadd(redis, stream_key, "message_end", {}, operation_id="op_1")

        # Turn 2 — should NOT carry over tool calls from turn 1
        await _xadd(redis, stream_key, "message_start", {}, operation_id="op_2")
        await _xadd(
            redis,
            stream_key,
            "assistant_message",
            {"messageId": "m2", "content": "turn2"},
            operation_id="op_2",
        )
        await _xadd(redis, stream_key, "message_end", {}, operation_id="op_2")

        messages = await read_stream_messages(redis, stream_id)
        assert len(messages) == 2
        assert "toolCalls" in messages[0]
        assert "toolCalls" not in messages[1]


class TestReadStreamThinkingEdgeCases:
    async def test_no_events_returns_none(self) -> None:
        redis = get_redis()
        result = await read_stream_thinking(redis, str(uuid4()))
        assert result is None

    async def test_all_tool_calls_completed_returns_none(self) -> None:
        redis = get_redis()
        stream_id = str(uuid4())
        stream_key = f"stream:{stream_id}"

        await _xadd(redis, stream_key, "message_start", {})
        await _xadd(
            redis,
            stream_key,
            "tool_call_start",
            {"id": "tc1", "name": "search"},
        )
        await _xadd(
            redis,
            stream_key,
            "tool_call_end",
            {"id": "tc1"},
        )

        result = await read_stream_thinking(redis, stream_id)
        # No message_end, but all tool calls are completed — no open tools
        assert result is None

    async def test_multiple_open_tool_calls(self) -> None:
        redis = get_redis()
        stream_id = str(uuid4())
        stream_key = f"stream:{stream_id}"

        await _xadd(redis, stream_key, "message_start", {})
        await _xadd(
            redis,
            stream_key,
            "tool_call_start",
            {"id": "tc1", "name": "search"},
        )
        await _xadd(
            redis,
            stream_key,
            "tool_call_start",
            {"id": "tc2", "name": "filter"},
        )

        result = await read_stream_thinking(redis, stream_id)
        assert result is not None
        assert len(result["toolCalls"]) == 2

    async def test_malformed_tool_call_data_skipped(self) -> None:
        """Malformed JSON in tool_call_start should not crash thinking detection."""
        redis = get_redis()
        stream_id = str(uuid4())
        stream_key = f"stream:{stream_id}"

        await _xadd(redis, stream_key, "message_start", {})
        # Malformed tool_call_start
        await _xadd_raw(
            redis,
            stream_key,
            {
                b"op": b"op_1",
                b"type": b"tool_call_start",
                b"data": b"not valid json",
            },
        )
        # Valid tool_call_start
        await _xadd(
            redis,
            stream_key,
            "tool_call_start",
            {"id": "tc2", "name": "valid"},
        )

        result = await read_stream_thinking(redis, stream_id)
        assert result is not None
        assert len(result["toolCalls"]) == 1
        assert result["toolCalls"][0]["name"] == "valid"

    async def test_second_turn_overrides_first(self) -> None:
        """If there are two message_start events, only the last one matters."""
        redis = get_redis()
        stream_id = str(uuid4())
        stream_key = f"stream:{stream_id}"

        # Turn 1 (completed)
        await _xadd(
            redis, stream_key, "message_start", {}, operation_id="op_1"
        )
        await _xadd(
            redis,
            stream_key,
            "tool_call_start",
            {"id": "tc1", "name": "old_tool"},
            operation_id="op_1",
        )
        await _xadd(redis, stream_key, "message_end", {}, operation_id="op_1")

        # Turn 2 (active)
        await _xadd(
            redis, stream_key, "message_start", {}, operation_id="op_2"
        )
        await _xadd(
            redis,
            stream_key,
            "tool_call_start",
            {"id": "tc2", "name": "new_tool"},
            operation_id="op_2",
        )

        result = await read_stream_thinking(redis, stream_id)
        assert result is not None
        # Should show only the active turn's tool calls
        assert len(result["toolCalls"]) == 1
        assert result["toolCalls"][0]["name"] == "new_tool"


class TestEmitEdgeCases:
    """emit() edge cases using real Redis."""

    async def test_emit_with_none_operation_id(self) -> None:
        redis = get_redis()
        stream_id = f"test-emit-{uuid4().hex[:8]}"

        entry_id = await emit(redis, stream_id, None, "test", {"key": "value"})
        assert isinstance(entry_id, str)
        assert "-" in entry_id  # Redis entry ID format: timestamp-sequence

        # Verify the event was actually written
        entries = await redis.xrange(f"stream:{stream_id}")
        assert len(entries) == 1
        fields = entries[0][1]
        assert fields[b"op"] == b""

    async def test_emit_serializes_non_json_types_with_default_str(self) -> None:
        """datetime and other non-JSON types should be serialized via default=str."""
        redis = get_redis()
        stream_id = f"test-emit-{uuid4().hex[:8]}"

        now = datetime.now(UTC)
        entry_id = await emit(redis, stream_id, "op_1", "test", {"timestamp": now})
        assert isinstance(entry_id, str)

        # Verify serialized data
        entries = await redis.xrange(f"stream:{stream_id}")
        assert len(entries) == 1
        data = json.loads(entries[0][1][b"data"])
        assert isinstance(data["timestamp"], str)
