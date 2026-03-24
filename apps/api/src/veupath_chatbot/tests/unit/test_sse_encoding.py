"""Tests for SSE stream encoding, error handling, and edge cases.

Covers:
- Newline handling in SSE data field
- Non-JSON-serializable data
- Producer exceptions before sending end event
- Empty event types
- Large payloads
- Task lifecycle (cancel behavior)
- Multiple end event types
"""

import asyncio
import json
from datetime import UTC, datetime

import pytest

from veupath_chatbot.transport.http.sse import SSE_HEADERS, sse_stream

# ---------------------------------------------------------------------------
# SSE frame format verification
# ---------------------------------------------------------------------------


class TestSSEFrameFormat:
    async def test_frame_format_is_valid_sse(self) -> None:
        """Each frame must be: event: <type>\ndata: <json>\n\n"""

        async def producer(send):
            await send({"type": "progress", "data": {"step": 1}})
            await send({"type": "done", "data": {}})

        async for frame in sse_stream(producer, {"done"}):
            lines = frame.split("\n")
            # Format: "event: ...", "data: ...", "", ""
            assert lines[0].startswith("event: ")
            assert lines[1].startswith("data: ")
            # Frame ends with double newline
            assert frame.endswith("\n\n")

    async def test_data_is_valid_json(self) -> None:
        """The data field must be valid JSON."""

        async def producer(send):
            await send({"type": "test", "data": {"key": "value", "num": 42}})
            await send({"type": "done", "data": {}})

        async for frame in sse_stream(producer, {"done"}):
            data_line = frame.split("\n")[1]
            json_str = data_line.removeprefix("data: ")
            parsed = json.loads(json_str)
            assert isinstance(parsed, dict)


# ---------------------------------------------------------------------------
# Newline handling in data
# BUG: If event data contains values with newlines, json.dumps escapes them
# as \n (literal backslash-n), which is correct. But if raw strings with
# actual newlines were interpolated into the SSE frame, they would break
# the protocol. json.dumps prevents this, but it's worth verifying.
# ---------------------------------------------------------------------------


class TestSSENewlineHandling:
    async def test_newlines_in_data_values_are_json_escaped(self) -> None:
        """Newlines in data values are escaped by json.dumps."""

        async def producer(send):
            await send({"type": "msg", "data": {"content": "line1\nline2\nline3"}})
            await send({"type": "done", "data": {}})

        frames = [frame async for frame in sse_stream(producer, {"done"})]

        # The first frame's data line should have escaped newlines
        data_line = frames[0].split("\n")[1]
        json_str = data_line.removeprefix("data: ")

        # json.dumps produces \\n (escaped), not bare newlines
        assert "\\n" in json_str
        # The raw frame should NOT have bare newlines within the data section
        # (only the structural SSE newlines)
        parsed = json.loads(json_str)
        assert parsed["content"] == "line1\nline2\nline3"

    async def test_multiline_string_doesnt_break_sse(self) -> None:
        """A multi-line string in data should produce a valid single-line data field."""
        multiline = "First paragraph.\n\nSecond paragraph.\n\nThird."

        async def producer(send):
            await send({"type": "msg", "data": {"text": multiline}})
            await send({"type": "done", "data": {}})

        frames = [frame async for frame in sse_stream(producer, {"done"})]

        # Parse the first frame and verify content roundtrips
        data_line = frames[0].split("\n")[1]
        parsed = json.loads(data_line.removeprefix("data: "))
        assert parsed["text"] == multiline


# ---------------------------------------------------------------------------
# Producer error handling
# A crashing producer now injects an ``internal_error`` sentinel event so
# the consumer never blocks indefinitely.
# ---------------------------------------------------------------------------


class TestSSEProducerErrors:
    async def test_producer_exception_injects_error_event(self) -> None:
        """A producer crash injects an internal_error event and terminates."""

        async def failing_producer(send):
            await send({"type": "progress", "data": {"step": 1}})
            msg = "Producer crashed!"
            raise ValueError(msg)

        frames = [
            frame async for frame in sse_stream(failing_producer, {"done", "error"})
        ]

        assert len(frames) == 2
        assert "event: progress" in frames[0]
        assert "event: internal_error" in frames[1]
        # Raw exception message must NOT leak — sanitized to generic message
        assert "Producer crashed!" not in frames[1]
        assert "An internal error occurred" in frames[1]


# ---------------------------------------------------------------------------
# Non-JSON-serializable data
# BUG: If data contains non-serializable objects (e.g., datetime, set),
# json.dumps will raise TypeError. This exception would propagate up
# through the async generator, potentially without sending an end event.
# ---------------------------------------------------------------------------


class TestSSENonSerializableData:
    async def test_non_serializable_data_raises(self) -> None:
        """Non-JSON-serializable data in events crashes the stream."""

        async def producer(send):
            # datetime is not JSON-serializable by default
            await send({"type": "msg", "data": {"time": datetime.now(tz=UTC)}})
            await send({"type": "done", "data": {}})

        with pytest.raises(TypeError, match="not JSON serializable"):
            async for _ in sse_stream(producer, {"done"}):
                pass

    async def test_set_in_data_raises(self) -> None:
        """Sets are not JSON-serializable."""

        async def producer(send):
            await send({"type": "msg", "data": {"items": {1, 2, 3}}})
            await send({"type": "done", "data": {}})

        with pytest.raises(TypeError):
            async for _ in sse_stream(producer, {"done"}):
                pass


# ---------------------------------------------------------------------------
# Edge case: empty or missing fields in events
# ---------------------------------------------------------------------------


class TestSSEEventFieldDefaults:
    async def test_missing_type_defaults_to_experiment_progress(self) -> None:
        async def producer(send):
            await send({"data": {"value": 1}})
            await send({"type": "done", "data": {}})

        frames = [frame async for frame in sse_stream(producer, {"done"})]

        assert frames[0].startswith("event: experiment_progress\n")

    async def test_missing_data_defaults_to_empty_dict(self) -> None:
        async def producer(send):
            await send({"type": "done"})

        frames = [frame async for frame in sse_stream(producer, {"done"})]

        assert "data: {}" in frames[0]

    async def test_completely_empty_event(self) -> None:
        """An empty dict event uses both defaults."""

        async def producer(send):
            await send({})
            await send({"type": "done", "data": {}})

        frames = [frame async for frame in sse_stream(producer, {"done"})]

        assert frames[0] == "event: experiment_progress\ndata: {}\n\n"

    async def test_event_type_with_spaces(self) -> None:
        """Event type with spaces is technically valid SSE but unusual."""

        async def producer(send):
            await send({"type": "my event type", "data": {}})
            await send({"type": "done", "data": {}})

        frames = [frame async for frame in sse_stream(producer, {"done"})]

        assert "event: my event type" in frames[0]


# ---------------------------------------------------------------------------
# Large payloads
# ---------------------------------------------------------------------------


class TestSSELargePayloads:
    async def test_large_data_payload(self) -> None:
        """Large data payloads should be serialized without issues."""
        large_list = [{"id": f"item_{i}", "value": i} for i in range(10_000)]

        async def producer(send):
            await send({"type": "data", "data": {"items": large_list}})
            await send({"type": "done", "data": {}})

        frames = [frame async for frame in sse_stream(producer, {"done"})]

        data_line = frames[0].split("\n")[1]
        parsed = json.loads(data_line.removeprefix("data: "))
        assert len(parsed["items"]) == 10_000


# ---------------------------------------------------------------------------
# Task lifecycle
# ---------------------------------------------------------------------------


class TestSSETaskLifecycle:
    async def test_task_cancelled_after_end_event(self) -> None:
        """The producer task should be cancelled after the stream ends."""
        task_was_cancelled = False

        async def slow_producer(send):
            nonlocal task_was_cancelled
            await send({"type": "done", "data": {}})
            try:
                await asyncio.sleep(100)
            except asyncio.CancelledError:
                task_was_cancelled = True
                raise

        [frame async for frame in sse_stream(slow_producer, {"done"})]

        # Give the event loop a chance to process the cancellation
        await asyncio.sleep(0.1)
        assert task_was_cancelled

    async def test_many_events_before_end(self) -> None:
        """Stream handles many events before the end event."""

        async def producer(send):
            for i in range(100):
                await send({"type": "progress", "data": {"step": i}})
            await send({"type": "done", "data": {"total": 100}})

        frames = [frame async for frame in sse_stream(producer, {"done"})]

        assert len(frames) == 101  # 100 progress + 1 done
        # Verify last frame is the done event
        assert "done" in frames[-1]


# ---------------------------------------------------------------------------
# SSE_HEADERS constant
# ---------------------------------------------------------------------------


class TestSSEHeaders:
    def test_all_required_headers_present(self) -> None:
        assert "Cache-Control" in SSE_HEADERS
        assert "Connection" in SSE_HEADERS
        assert "X-Accel-Buffering" in SSE_HEADERS

    def test_header_values(self) -> None:
        assert SSE_HEADERS["Cache-Control"] == "no-cache"
        assert SSE_HEADERS["Connection"] == "keep-alive"
        assert SSE_HEADERS["X-Accel-Buffering"] == "no"

    def test_no_content_type_header(self) -> None:
        # Content-Type should be set by FastAPI's StreamingResponse,
        # not in SSE_HEADERS. Verify it's not doubled.
        assert "Content-Type" not in SSE_HEADERS
