"""Tests for Redis Stream emission observability helpers."""

from unittest.mock import AsyncMock, patch

import pytest

from pathfinder.platform.redis_streams import StreamAppendRequest, append_stream_event


@pytest.mark.asyncio
async def test_append_stream_event_records_success_metrics() -> None:
    redis = AsyncMock()
    redis.xadd.return_value = "1710000000000-0"
    request = StreamAppendRequest(
        stream_key="stream:abc",
        operation_id="op_123",
        event_type="assistant_delta",
        event_data={"delta": "hello"},
        maxlen=50_000,
        approximate=True,
        projected=True,
        committed=False,
    )

    with (
        patch("pathfinder.platform.redis_streams.redis_stream_emit_attempts") as mock_attempts,
        patch(
            "pathfinder.platform.redis_streams.redis_stream_emit_duration_s"
        ) as mock_duration,
        patch(
            "pathfinder.platform.redis_streams.redis_stream_events_emitted"
        ) as mock_emitted,
    ):
        entry_id = await append_stream_event(redis, request)

    assert entry_id == "1710000000000-0"
    expected_attrs = {
        "stream_kind": "conversation",
        "event_type": "assistant_delta",
        "projected": "true",
        "committed": "false",
    }
    mock_attempts.add.assert_called_once_with(1, {**expected_attrs, "outcome": "ok"})
    mock_duration.record.assert_called_once()
    mock_emitted.add.assert_called_once_with(1, expected_attrs)


@pytest.mark.asyncio
async def test_append_stream_event_records_error_metrics() -> None:
    redis = AsyncMock()
    redis.xadd.side_effect = RuntimeError("redis down")
    request = StreamAppendRequest(
        stream_key="op:op_123",
        operation_id="op_123",
        event_type="experiment_error",
        event_data={"error": "boom"},
        maxlen=10_000,
        approximate=True,
    )

    with (
        patch("pathfinder.platform.redis_streams.redis_stream_emit_attempts") as mock_attempts,
        patch(
            "pathfinder.platform.redis_streams.redis_stream_emit_duration_s"
        ) as mock_duration,
        patch(
            "pathfinder.platform.redis_streams.redis_stream_events_emitted"
        ) as mock_emitted,
        pytest.raises(RuntimeError, match="redis down"),
    ):
        await append_stream_event(redis, request)

    expected_attrs = {
        "stream_kind": "operation",
        "event_type": "experiment_error",
        "projected": "false",
        "committed": "false",
        "outcome": "error",
    }
    mock_attempts.add.assert_called_once_with(1, expected_attrs)
    mock_duration.record.assert_called_once()
    mock_emitted.add.assert_not_called()
