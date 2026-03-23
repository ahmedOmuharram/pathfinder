"""Extended event system tests — edge cases for event parsing and projection.

Focuses on:
- _parse_arguments edge cases (non-dict JSON, numbers, arrays, nested)
- _entry_id_to_iso edge cases (invalid entry IDs, boundary timestamps)
- read_stream_messages with malformed event data
- read_stream_thinking with edge cases
- Projection skipping for non-projected event types
"""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from veupath_chatbot.platform.events import (
    _entry_id_to_iso,
    _project_event,
    emit,
    read_stream_messages,
    read_stream_thinking,
)


class TestEntryIdToIso:
    """_entry_id_to_iso converts Redis entry IDs to ISO 8601 timestamps."""

    def test_valid_entry_id(self):
        # 1709234567890 ms = some specific datetime
        result = _entry_id_to_iso("1709234567890-0")
        assert result.endswith(("+00:00", "Z"))
        # Should parse as a valid ISO 8601 datetime
        dt = datetime.fromisoformat(result)
        assert dt.tzinfo is not None

    def test_bytes_entry_id(self):
        result = _entry_id_to_iso(b"1709234567890-0")
        dt = datetime.fromisoformat(result)
        assert dt.tzinfo is not None

    def test_invalid_entry_id_returns_now(self):
        """Non-numeric entry ID should fall back to current time."""
        result = _entry_id_to_iso("invalid-entry-id")
        dt = datetime.fromisoformat(result)
        # Should be approximately now
        diff = abs((datetime.now(UTC) - dt).total_seconds())
        assert diff < 5

    def test_zero_timestamp(self):
        result = _entry_id_to_iso("0-0")
        dt = datetime.fromisoformat(result)
        # Unix epoch
        assert dt.year == 1970

    def test_entry_id_without_sequence(self):
        """Entry ID with no '-N' suffix — split('-')[0] still works."""
        result = _entry_id_to_iso("1709234567890")
        dt = datetime.fromisoformat(result)
        assert dt.tzinfo is not None


class TestReadStreamMessagesEdgeCases:
    """Edge cases for read_stream_messages."""

    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        redis.xrange = AsyncMock(return_value=[])
        return redis

    async def test_empty_stream(self, mock_redis):
        messages = await read_stream_messages(mock_redis, str(uuid4()))
        assert messages == []

    async def test_malformed_data_skipped(self, mock_redis):
        """Events with invalid JSON data should be skipped without crashing."""
        mock_redis.xrange.return_value = [
            (
                b"1-0",
                {
                    b"op": b"op_1",
                    b"type": b"user_message",
                    b"data": b"not valid json {{{",
                },
            ),
            (
                b"2-0",
                {
                    b"op": b"op_1",
                    b"type": b"assistant_message",
                    b"data": json.dumps(
                        {"messageId": "m1", "content": "hello"}
                    ).encode(),
                },
            ),
        ]

        messages = await read_stream_messages(mock_redis, str(uuid4()))
        # The malformed user_message is skipped; only assistant_message remains
        assert len(messages) == 1
        assert messages[0]["role"] == "assistant"

    async def test_missing_data_field_skipped(self, mock_redis):
        """Events without a b'data' key should be skipped."""
        mock_redis.xrange.return_value = [
            (
                b"1-0",
                {
                    b"op": b"op_1",
                    b"type": b"user_message",
                    # no b"data" key
                },
            ),
            (
                b"2-0",
                {
                    b"op": b"op_1",
                    b"type": b"assistant_message",
                    b"data": json.dumps({"content": "hi"}).encode(),
                },
            ),
        ]

        messages = await read_stream_messages(mock_redis, str(uuid4()))
        assert len(messages) == 1
        assert messages[0]["role"] == "assistant"

    async def test_assistant_message_with_empty_content(self, mock_redis):
        mock_redis.xrange.return_value = [
            (
                b"1-0",
                {
                    b"op": b"op_1",
                    b"type": b"assistant_message",
                    b"data": json.dumps({"messageId": "m1"}).encode(),
                },
            ),
        ]

        messages = await read_stream_messages(mock_redis, str(uuid4()))
        assert len(messages) == 1
        assert messages[0]["content"] == ""

    async def test_planning_artifacts_aggregated(self, mock_redis):
        mock_redis.xrange.return_value = [
            (b"1-0", {b"op": b"op_1", b"type": b"message_start", b"data": b"{}"}),
            (
                b"2-0",
                {
                    b"op": b"op_1",
                    b"type": b"planning_artifact",
                    b"data": json.dumps(
                        {"planningArtifact": {"type": "plan", "steps": [1, 2]}}
                    ).encode(),
                },
            ),
            (
                b"3-0",
                {
                    b"op": b"op_1",
                    b"type": b"assistant_message",
                    b"data": json.dumps(
                        {"messageId": "m1", "content": "done"}
                    ).encode(),
                },
            ),
            (b"4-0", {b"op": b"op_1", b"type": b"message_end", b"data": b"{}"}),
        ]

        messages = await read_stream_messages(mock_redis, str(uuid4()))
        assert len(messages) == 1
        assert "planningArtifacts" in messages[0]
        assert len(messages[0]["planningArtifacts"]) == 1

    async def test_turn_reset_on_message_end(self, mock_redis):
        """Turn accumulators should reset after message_end."""
        mock_redis.xrange.return_value = [
            # Turn 1
            (b"1-0", {b"op": b"op_1", b"type": b"message_start", b"data": b"{}"}),
            (
                b"2-0",
                {
                    b"op": b"op_1",
                    b"type": b"tool_call_start",
                    b"data": json.dumps({"id": "tc1", "name": "tool_a"}).encode(),
                },
            ),
            (
                b"3-0",
                {
                    b"op": b"op_1",
                    b"type": b"assistant_message",
                    b"data": json.dumps(
                        {"messageId": "m1", "content": "turn1"}
                    ).encode(),
                },
            ),
            (b"4-0", {b"op": b"op_1", b"type": b"message_end", b"data": b"{}"}),
            # Turn 2 — should NOT carry over tool calls from turn 1
            (b"5-0", {b"op": b"op_2", b"type": b"message_start", b"data": b"{}"}),
            (
                b"6-0",
                {
                    b"op": b"op_2",
                    b"type": b"assistant_message",
                    b"data": json.dumps(
                        {"messageId": "m2", "content": "turn2"}
                    ).encode(),
                },
            ),
            (b"7-0", {b"op": b"op_2", b"type": b"message_end", b"data": b"{}"}),
        ]

        messages = await read_stream_messages(mock_redis, str(uuid4()))
        assert len(messages) == 2
        assert "toolCalls" in messages[0]
        assert "toolCalls" not in messages[1]


class TestReadStreamThinkingEdgeCases:
    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        redis.xrange = AsyncMock(return_value=[])
        return redis

    async def test_no_events_returns_none(self, mock_redis):
        result = await read_stream_thinking(mock_redis, str(uuid4()))
        assert result is None

    async def test_all_tool_calls_completed_returns_none(self, mock_redis):
        mock_redis.xrange.return_value = [
            (b"1-0", {b"op": b"op_1", b"type": b"message_start", b"data": b"{}"}),
            (
                b"2-0",
                {
                    b"op": b"op_1",
                    b"type": b"tool_call_start",
                    b"data": json.dumps({"id": "tc1", "name": "search"}).encode(),
                },
            ),
            (
                b"3-0",
                {
                    b"op": b"op_1",
                    b"type": b"tool_call_end",
                    b"data": json.dumps({"id": "tc1"}).encode(),
                },
            ),
        ]

        result = await read_stream_thinking(mock_redis, str(uuid4()))
        # No message_end, but all tool calls are completed — no open tools
        assert result is None

    async def test_multiple_open_tool_calls(self, mock_redis):
        mock_redis.xrange.return_value = [
            (b"1-0", {b"op": b"op_1", b"type": b"message_start", b"data": b"{}"}),
            (
                b"2-0",
                {
                    b"op": b"op_1",
                    b"type": b"tool_call_start",
                    b"data": json.dumps({"id": "tc1", "name": "search"}).encode(),
                },
            ),
            (
                b"3-0",
                {
                    b"op": b"op_1",
                    b"type": b"tool_call_start",
                    b"data": json.dumps({"id": "tc2", "name": "filter"}).encode(),
                },
            ),
        ]

        result = await read_stream_thinking(mock_redis, str(uuid4()))
        assert result is not None
        assert len(result["toolCalls"]) == 2

    async def test_malformed_tool_call_data_skipped(self, mock_redis):
        """Malformed JSON in tool_call_start should not crash thinking detection."""
        mock_redis.xrange.return_value = [
            (b"1-0", {b"op": b"op_1", b"type": b"message_start", b"data": b"{}"}),
            (
                b"2-0",
                {
                    b"op": b"op_1",
                    b"type": b"tool_call_start",
                    b"data": b"not valid json",
                },
            ),
            (
                b"3-0",
                {
                    b"op": b"op_1",
                    b"type": b"tool_call_start",
                    b"data": json.dumps({"id": "tc2", "name": "valid"}).encode(),
                },
            ),
        ]

        result = await read_stream_thinking(mock_redis, str(uuid4()))
        assert result is not None
        assert len(result["toolCalls"]) == 1
        assert result["toolCalls"][0]["name"] == "valid"

    async def test_second_turn_overrides_first(self, mock_redis):
        """If there are two message_start events, only the last one matters."""
        mock_redis.xrange.return_value = [
            # Turn 1 (completed)
            (b"1-0", {b"op": b"op_1", b"type": b"message_start", b"data": b"{}"}),
            (
                b"2-0",
                {
                    b"op": b"op_1",
                    b"type": b"tool_call_start",
                    b"data": json.dumps({"id": "tc1", "name": "old_tool"}).encode(),
                },
            ),
            (b"3-0", {b"op": b"op_1", b"type": b"message_end", b"data": b"{}"}),
            # Turn 2 (active)
            (b"4-0", {b"op": b"op_2", b"type": b"message_start", b"data": b"{}"}),
            (
                b"5-0",
                {
                    b"op": b"op_2",
                    b"type": b"tool_call_start",
                    b"data": json.dumps({"id": "tc2", "name": "new_tool"}).encode(),
                },
            ),
        ]

        result = await read_stream_thinking(mock_redis, str(uuid4()))
        assert result is not None
        # Should show only the active turn's tool calls
        assert len(result["toolCalls"]) == 1
        assert result["toolCalls"][0]["name"] == "new_tool"


class TestProjectionSkipping:
    """Non-projected event types should not trigger DB writes."""

    @pytest.fixture
    def mock_session(self):
        session = AsyncMock()
        session.execute = AsyncMock()
        session.flush = AsyncMock()
        return session

    async def test_assistant_delta_not_projected(self, mock_session):
        """High-frequency events like assistant_delta should not hit DB."""
        await _project_event(
            mock_session,
            str(uuid4()),
            "assistant_delta",
            {"content": "tok"},
            "1-0",
        )
        mock_session.execute.assert_not_called()

    async def test_tool_call_start_not_projected(self, mock_session):
        await _project_event(
            mock_session,
            str(uuid4()),
            "tool_call_start",
            {"id": "tc1"},
            "1-0",
        )
        mock_session.execute.assert_not_called()

    async def test_user_message_is_projected(self, mock_session):
        await _project_event(
            mock_session,
            str(uuid4()),
            "user_message",
            {"content": "hello"},
            "1-0",
        )
        mock_session.execute.assert_called_once()
        mock_session.flush.assert_called_once()

    async def test_model_selected_is_projected(self, mock_session):
        await _project_event(
            mock_session,
            str(uuid4()),
            "model_selected",
            {"modelId": "gpt-5"},
            "1-0",
        )
        mock_session.execute.assert_called_once()


class TestEmitEdgeCases:
    async def test_emit_with_none_operation_id(self):
        redis = AsyncMock()
        redis.xadd = AsyncMock(return_value=b"1-0")

        entry_id = await emit(redis, "stream-1", None, "test", {"key": "value"})
        assert entry_id == "1-0"

        call_args = redis.xadd.call_args
        fields = call_args[0][1]
        assert fields["op"] == b""

    async def test_emit_string_entry_id(self):
        """If Redis returns a string entry ID instead of bytes."""
        redis = AsyncMock()
        redis.xadd = AsyncMock(return_value="1709234567890-0")

        entry_id = await emit(redis, "stream-1", "op_1", "test", {})
        assert entry_id == "1709234567890-0"

    async def test_emit_serializes_non_json_types_with_default_str(self):
        """datetime and other non-JSON types should be serialized via default=str."""
        redis = AsyncMock()
        redis.xadd = AsyncMock(return_value=b"1-0")

        now = datetime.now(UTC)
        await emit(redis, "stream-1", "op_1", "test", {"timestamp": now})

        call_args = redis.xadd.call_args
        data_bytes = call_args[0][1]["data"]
        data = json.loads(data_bytes)
        assert isinstance(data["timestamp"], str)
