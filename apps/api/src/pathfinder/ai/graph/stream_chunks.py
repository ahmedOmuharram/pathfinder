from __future__ import annotations

import json
from typing import Any

from pydantic_ai.ui.vercel_ai.response_types import (
    BaseChunk,
    DataChunk,
    ErrorChunk,
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


def error_chunk(text: str) -> ErrorChunk:
    """Build an AI SDK v6 ``ErrorChunk`` surfacing a server-side failure.

    The client's ``useChat`` sets its ``error`` field when it receives one of
    these; the chat UI renders a distinct error bubble.
    """
    return ErrorChunk(error_text=text)


def background_task_started_chunk(
    *,
    task_id: str,
    tool_name: str,
    estimated_duration_seconds: int,
) -> DataChunk:
    """Signal that a durable tool has been dispatched and the graph is paused.

    The UI keeps the stream open and displays a progress panel until the
    worker resumes the graph (or the task is cancelled).
    """
    return DataChunk(
        type="data-background-task-started",
        data={
            "taskId": task_id,
            "toolName": tool_name,
            "estimatedDurationSeconds": estimated_duration_seconds,
        },
    )


def encode_chunk_as_sse(chunk: BaseChunk) -> str:
    payload = chunk.model_dump(by_alias=True, exclude_none=True, mode="json")
    return f"data: {json.dumps(payload)}\n\n"
