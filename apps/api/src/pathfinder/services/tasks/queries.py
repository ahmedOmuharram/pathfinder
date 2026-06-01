"""Read queries for durable tasks + their progress rows.

Owns all ``background_tasks`` / ``task_progress`` access so the transport
task router never imports persistence.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select

from pathfinder.persistence.models import BackgroundTask, TaskProgress
from pathfinder.platform.db import async_session_factory
from pathfinder.platform.errors import NotFoundError

_TERMINAL_TASK_STATUSES: frozenset[str] = frozenset({"complete", "failed"})


@dataclass(frozen=True)
class TaskRow:
    id: UUID
    tool_name: str
    status: str
    estimated_duration_seconds: int
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    result: Any
    error: str | None


@dataclass(frozen=True)
class ProgressRow:
    id: int
    task_id: UUID
    percent: float
    message: str
    data: dict[str, Any] | None
    emitted_at: datetime


def _to_task_row(t: BackgroundTask) -> TaskRow:
    return TaskRow(
        id=t.id,
        tool_name=t.tool_name,
        status=t.status,
        estimated_duration_seconds=t.estimated_duration_seconds,
        created_at=t.created_at,
        started_at=t.started_at,
        completed_at=t.completed_at,
        result=t.result,
        error=t.error,
    )


def _to_progress_row(p: TaskProgress) -> ProgressRow:
    return ProgressRow(
        id=p.id,
        task_id=p.task_id,
        percent=p.percent,
        message=p.message,
        data=p.data,
        emitted_at=p.emitted_at,
    )


async def load_task(*, conversation_id: UUID, task_id: UUID, user_id: UUID) -> TaskRow:
    async with async_session_factory() as session:
        task = (
            await session.execute(
                select(BackgroundTask).where(
                    BackgroundTask.id == task_id,
                    BackgroundTask.conversation_id == conversation_id,
                    BackgroundTask.user_id == user_id,
                ),
            )
        ).scalar_one_or_none()
    if task is None:
        raise NotFoundError(title="task not found")
    return _to_task_row(task)


async def list_task_rows(
    *,
    conversation_id: UUID,
    user_id: UUID,
    statuses: set[str] | None,
) -> list[TaskRow]:
    async with async_session_factory() as session:
        query = (
            select(BackgroundTask)
            .where(
                BackgroundTask.conversation_id == conversation_id,
                BackgroundTask.user_id == user_id,
            )
            .order_by(BackgroundTask.created_at.desc())
        )
        if statuses:
            query = query.where(BackgroundTask.status.in_(statuses))
        rows = (await session.execute(query)).scalars().all()
    return [_to_task_row(t) for t in rows]


async def latest_progress_by_task(task_ids: list[UUID]) -> dict[UUID, ProgressRow]:
    if not task_ids:
        return {}
    async with async_session_factory() as session:
        rows = (
            (
                await session.execute(
                    select(TaskProgress)
                    .where(TaskProgress.task_id.in_(task_ids))
                    .order_by(TaskProgress.id.desc()),
                )
            )
            .scalars()
            .all()
        )
    latest: dict[UUID, ProgressRow] = {}
    for row in rows:
        latest.setdefault(row.task_id, _to_progress_row(row))
    return latest


async def progress_rows(task_id: UUID, *, after_id: int = 0) -> list[ProgressRow]:
    async with async_session_factory() as session:
        rows = (
            (
                await session.execute(
                    select(TaskProgress)
                    .where(TaskProgress.task_id == task_id, TaskProgress.id > after_id)
                    .order_by(TaskProgress.id),
                )
            )
            .scalars()
            .all()
        )
    return [_to_progress_row(r) for r in rows]


async def terminal_status(task_id: UUID) -> tuple[str, str | None] | None:
    """Return ``(status, error)`` if the task reached a terminal status, else None."""
    async with async_session_factory() as session:
        task = (
            await session.execute(
                select(BackgroundTask).where(BackgroundTask.id == task_id),
            )
        ).scalar_one_or_none()
    if task is None or task.status not in _TERMINAL_TASK_STATUSES:
        return None
    return task.status, task.error
