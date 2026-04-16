from __future__ import annotations

from uuid import UUID

from shared_py.stream_events import CustomEvent


def phase_start_event(*, phase: str, trace_id: str, model: str) -> CustomEvent:
    return CustomEvent(
        kind="data-phase-start",
        data={"phase": phase, "traceId": trace_id, "model": model},
    )


def phase_finish_event(*, phase: str, reason: str) -> CustomEvent:
    return CustomEvent(
        kind="data-phase-finish",
        data={"phase": phase, "reason": reason},
    )


def phase_change_event(*, phase: str, status: str, reason: str) -> CustomEvent:
    return CustomEvent(
        kind="data-phase-change",
        data={"phase": phase, "status": status, "reason": reason},
    )


def background_task_started_event(
    *,
    task_id: UUID,
    tool_name: str,
    estimated_duration_seconds: int,
) -> CustomEvent:
    return CustomEvent(
        kind="data-background-task-started",
        data={
            "taskId": str(task_id),
            "toolName": tool_name,
            "estimatedDurationSeconds": estimated_duration_seconds,
        },
    )
