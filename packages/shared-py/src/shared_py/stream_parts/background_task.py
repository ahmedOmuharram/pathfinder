"""Typed payloads for durable-task data-parts.

Three part types:
- ``data-background-task-started``: fired when a durable tool suspends the
  graph. Frontend opens a ``TaskCardPart``.
- ``data-task-progress``: incremental progress updates pushed through the
  task events SSE stream.
- ``data-task-completed``: terminal chunk when the worker finishes / fails.
"""

from __future__ import annotations

from typing import Any, Literal

from shared_py.pydantic_base import CamelModel


class BackgroundTaskStarted(CamelModel):
    task_id: str
    tool_name: str
    estimated_duration_seconds: int


class TaskProgress(CamelModel):
    task_id: str
    percent: float
    message: str
    tool_specific: dict[str, Any] | None = None


class TaskCompleted(CamelModel):
    task_id: str
    status: Literal["success", "failed"]
    error: str | None = None
