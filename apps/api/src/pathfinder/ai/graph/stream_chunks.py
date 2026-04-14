from __future__ import annotations

import json
from typing import Any

from pydantic_ai.ui.vercel_ai.response_types import (
    BaseChunk,
    FinishChunk,
    MessageMetadataChunk,
    StartChunk,
)

SSE_DONE_LINE: str = "data: [DONE]\n\n"


def phase_start_chunk(
    *,
    message_id: str,
    phase: str,
    model_name: str,
    trace_id: str,
    created_at: str,
    chat_id: str,
) -> StartChunk:
    metadata: dict[str, Any] = {
        "phase": phase,
        "model": model_name,
        "traceId": trace_id,
        "createdAt": created_at,
        "chatId": chat_id,
    }
    return StartChunk(message_id=message_id, message_metadata=metadata)


def phase_finish_chunk(*, reason: str) -> FinishChunk:
    return FinishChunk(finish_reason=reason)


def title_metadata_chunk(title: str) -> MessageMetadataChunk:
    return MessageMetadataChunk(message_metadata={"conversationTitle": title})


def encode_chunk_as_sse(chunk: BaseChunk) -> str:
    payload = chunk.model_dump(by_alias=True, exclude_none=True, mode="json")
    return f"data: {json.dumps(payload)}\n\n"
