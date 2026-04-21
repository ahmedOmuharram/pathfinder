"""Helpers that produce AI SDK v6 ``DataChunk``s for chat telemetry.

Every ``data-*`` UI part the frontend renders starts life here or in a tool.
Emitted via ``get_stream_writer`` alongside the agent's v6 chunks so the
frontend sees them as native ``DataUIPart``s on the assistant message.
"""
from __future__ import annotations

from uuid import UUID

from pydantic_ai.ui.vercel_ai.response_types import DataChunk


def phase_start_event(*, phase: str, trace_id: str, model: str) -> DataChunk:
    return DataChunk(
        type="data-phase-start",
        data={"phase": phase, "traceId": trace_id, "model": model},
    )


def phase_change_event(*, phase: str, status: str, reason: str) -> DataChunk:
    return DataChunk(
        type="data-phase-change",
        data={"phase": phase, "status": status, "reason": reason},
    )


def background_task_started_event(
    *,
    task_id: UUID,
    tool_name: str,
    estimated_duration_seconds: int,
) -> DataChunk:
    return DataChunk(
        type="data-background-task-started",
        data={
            "taskId": str(task_id),
            "toolName": tool_name,
            "estimatedDurationSeconds": estimated_duration_seconds,
        },
    )


def conversation_title_event(*, title: str) -> DataChunk:
    return DataChunk(
        type="data-conversation-title",
        data={"title": title},
    )


def turn_rejected_event(*, message: str, reason: str) -> DataChunk:
    return DataChunk(
        type="data-turn-rejected",
        data={"message": message, "reason": reason},
    )


def turn_qa_event(*, answer: str, reason: str) -> DataChunk:
    return DataChunk(
        type="data-turn-qa",
        data={"answer": answer, "reason": reason},
    )


def supervisor_decision_event(*, to: str, reason: str) -> DataChunk:
    return DataChunk(
        type="data-supervisor-decision",
        data={"to": to, "reason": reason},
    )


def scratchpad_updated_event() -> DataChunk:
    """Chunk that instructs the client to invalidate its scratchpad query."""
    return DataChunk(type="data-scratchpad-updated", data={})
