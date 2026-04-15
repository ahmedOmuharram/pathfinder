from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pathfinder.platform.pydantic_base import CamelModel


class TaskProgressEvent(CamelModel):
    task_id: UUID
    percent: float
    message: str
    data: dict[str, Any] | None = None
    emitted_at: datetime


class TaskStatusResponse(CamelModel):
    task_id: UUID
    tool_name: str
    status: str
    estimated_duration_seconds: int
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
