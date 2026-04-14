from __future__ import annotations

import json
from typing import Any

from pydantic_ai.ui.vercel_ai.response_types import (
    FinishChunk,
    MessageMetadataChunk,
    StartChunk,
)

from pathfinder.ai.graph.stream_chunks import (
    SSE_DONE_LINE,
    encode_chunk_as_sse,
    phase_finish_chunk,
    phase_start_chunk,
    title_metadata_chunk,
)


def _parse_sse_payload(line: str) -> dict[str, Any]:
    assert line.endswith("\n\n"), line
    raw = line.removeprefix("data: ").rstrip("\n")
    return json.loads(raw)


def test_phase_start_chunk_includes_metadata() -> None:
    chunk = phase_start_chunk(
        message_id="msg-1",
        phase="scoping",
        model_name="openai:gpt-4.1-mini",
        trace_id="trace-1",
        created_at="2026-04-14T00:00:00+00:00",
        chat_id="chat-uuid",
    )
    assert isinstance(chunk, StartChunk)
    assert chunk.message_id == "msg-1"
    assert chunk.message_metadata == {
        "phase": "scoping",
        "model": "openai:gpt-4.1-mini",
        "traceId": "trace-1",
        "createdAt": "2026-04-14T00:00:00+00:00",
        "chatId": "chat-uuid",
    }


def test_phase_finish_chunk_uses_provided_reason() -> None:
    chunk = phase_finish_chunk(reason="stop")
    assert isinstance(chunk, FinishChunk)
    assert chunk.finish_reason == "stop"


def test_title_metadata_chunk_carries_conversation_title() -> None:
    chunk = title_metadata_chunk("My Conversation")
    assert isinstance(chunk, MessageMetadataChunk)
    assert chunk.message_metadata == {"conversationTitle": "My Conversation"}


def test_encode_chunk_as_sse_emits_camelcased_json() -> None:
    chunk = phase_start_chunk(
        message_id="msg-1",
        phase="scoping",
        model_name="openai:gpt-4.1-mini",
        trace_id="trace-1",
        created_at="2026-04-14T00:00:00+00:00",
        chat_id="chat-uuid",
    )
    line = encode_chunk_as_sse(chunk)
    payload = _parse_sse_payload(line)
    assert payload["type"] == "start"
    assert payload["messageId"] == "msg-1"
    assert "messageMetadata" in payload
    assert payload["messageMetadata"]["traceId"] == "trace-1"
    assert payload["messageMetadata"]["createdAt"] == "2026-04-14T00:00:00+00:00"


def test_encode_chunk_excludes_none_values() -> None:
    line = encode_chunk_as_sse(phase_finish_chunk(reason="stop"))
    payload = _parse_sse_payload(line)
    assert payload == {"type": "finish", "finishReason": "stop"}


def test_sse_done_line_is_protocol_terminator() -> None:
    assert SSE_DONE_LINE == "data: [DONE]\n\n"
