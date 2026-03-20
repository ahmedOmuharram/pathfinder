"""Unit tests for transport.http.sse — SSE streaming helpers.

Focuses on:
- SSE frame formatting (event type, data encoding, double newline terminator)
- End-event detection (stream terminates on sentinel event types)
- Producer error handling
- Newlines/special characters in SSE data
- Task cancellation on stream end
- Queue-based flow control
"""

import asyncio
import json

from veupath_chatbot.transport.http.sse import SSE_HEADERS, sse_stream


class TestSSEHeaders:
    def test_headers_contain_no_cache(self):
        assert SSE_HEADERS["Cache-Control"] == "no-cache"

    def test_headers_contain_keep_alive(self):
        assert SSE_HEADERS["Connection"] == "keep-alive"

    def test_headers_disable_buffering(self):
        assert SSE_HEADERS["X-Accel-Buffering"] == "no"


class TestSSEStreamBasic:
    async def test_single_event_and_end(self):
        """Producer sends one progress event then an end event."""

        async def producer(send):
            await send({"type": "experiment_progress", "data": {"step": 1}})
            await send({"type": "experiment_complete", "data": {"result": "ok"}})

        frames = [
            frame async for frame in sse_stream(producer, {"experiment_complete"})
        ]

        assert len(frames) == 2
        assert (
            frames[0]
            == f"event: experiment_progress\ndata: {json.dumps({'step': 1})}\n\n"
        )
        assert (
            frames[1]
            == f"event: experiment_complete\ndata: {json.dumps({'result': 'ok'})}\n\n"
        )

    async def test_only_end_event(self):
        """Producer sends only the end event — stream should yield exactly one frame."""

        async def producer(send):
            await send({"type": "done", "data": {}})

        frames = [frame async for frame in sse_stream(producer, {"done"})]

        assert len(frames) == 1
        assert "event: done" in frames[0]

    async def test_multiple_progress_events_before_end(self):
        """Several progress events followed by the terminal event."""

        async def producer(send):
            for i in range(5):
                await send({"type": "progress", "data": {"i": i}})
            await send({"type": "complete", "data": {}})

        frames = [frame async for frame in sse_stream(producer, {"complete"})]

        assert len(frames) == 6
        assert "event: complete" in frames[-1]

    async def test_multiple_end_event_types(self):
        """Stream should stop on any of the specified end event types."""

        async def producer(send):
            await send({"type": "progress", "data": {}})
            await send({"type": "error", "data": {"message": "fail"}})

        frames = [frame async for frame in sse_stream(producer, {"complete", "error"})]

        assert len(frames) == 2
        assert "event: error" in frames[-1]


class TestSSEFrameFormat:
    async def test_frame_has_event_and_data_lines(self):
        """Each SSE frame must have 'event:' and 'data:' lines with double newline."""

        async def producer(send):
            await send({"type": "test_event", "data": {"key": "value"}})
            await send({"type": "end", "data": {}})

        async for frame in sse_stream(producer, {"end"}):
            assert frame.endswith("\n\n"), "SSE frames must end with double newline"
            lines = frame.strip().split("\n")
            assert lines[0].startswith("event: ")
            assert lines[1].startswith("data: ")
            break

    async def test_data_is_valid_json(self):
        """Data portion of SSE frame must be valid JSON."""

        async def producer(send):
            await send({"type": "test", "data": {"nested": {"a": [1, 2, 3]}}})
            await send({"type": "end", "data": {}})

        async for frame in sse_stream(producer, {"end"}):
            data_line = frame.strip().split("\n")[1]
            json_str = data_line.removeprefix("data: ")
            parsed = json.loads(json_str)
            assert parsed == {"nested": {"a": [1, 2, 3]}}
            break

    async def test_special_characters_in_data(self):
        """JSON-encoded data with special characters should be a single data: line.

        json.dumps produces a single line (no raw newlines), so SSE framing is safe.
        """

        async def producer(send):
            await send(
                {
                    "type": "test",
                    "data": {"text": "line1\nline2\ttab", "emoji": "test"},
                }
            )
            await send({"type": "end", "data": {}})

        async for frame in sse_stream(producer, {"end"}):
            # The JSON should encode newlines as \\n, not raw newlines
            assert "\\n" in frame  # escaped newline in JSON
            data_line = frame.strip().split("\n")[1]
            json_str = data_line.removeprefix("data: ")
            parsed = json.loads(json_str)
            assert parsed["text"] == "line1\nline2\ttab"
            break


class TestSSEDefaultEventType:
    async def test_missing_type_defaults_to_experiment_progress(self):
        """Events without a 'type' key use 'experiment_progress' as default."""

        async def producer(send):
            await send({"data": {"step": 1}})  # no type key
            await send({"type": "end", "data": {}})

        frames = [frame async for frame in sse_stream(producer, {"end"})]

        # First frame should use the default type
        assert "event: experiment_progress" in frames[0]

    async def test_missing_data_defaults_to_empty_dict(self):
        """Events without a 'data' key should produce 'data: {}'."""

        async def producer(send):
            await send({"type": "ping"})  # no data key
            await send({"type": "end", "data": {}})

        frames = [frame async for frame in sse_stream(producer, {"end"})]

        assert "data: {}" in frames[0]


class TestSSETaskCancellation:
    async def test_producer_task_cancelled_after_end(self):
        """The producer's asyncio task should be cancelled once the stream ends."""
        producer_cancelled = asyncio.Event()

        async def producer(send):
            await send({"type": "end", "data": {}})
            try:
                # Producer continues running after sending end...
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                producer_cancelled.set()
                raise

        async for _ in sse_stream(producer, {"end"}):
            pass

        # Give the cancellation a moment to propagate
        await asyncio.sleep(0.05)
        assert producer_cancelled.is_set(), (
            "Producer task was not cancelled after stream end"
        )

    async def test_producer_error_injects_internal_error_event(self):
        """If the producer crashes, an internal_error event terminates the stream."""

        async def producer(send):
            await send({"type": "progress", "data": {}})
            msg = "producer exploded"
            raise RuntimeError(msg)

        frames = [frame async for frame in sse_stream(producer, {"end"})]

        assert len(frames) == 2
        assert "event: progress" in frames[0]
        assert "event: internal_error" in frames[1]
        assert "producer exploded" in frames[1]
