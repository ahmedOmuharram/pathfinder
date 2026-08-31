"""Repository for durable background tasks dispatched to the Procrastinate worker.

Worker code has no long-lived ``AsyncSession`` — each mark/get operation opens
its own unit of work. Production callers pass ``async_session_factory`` (the
module-level factory attached to the test/app engine); tests can inject any
callable returning ``AsyncSession``.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.persistence.models import BackgroundTask

SessionFactory = Callable[[], AsyncSession]

ACTIVE_TASK_STATES = ("pending", "running", "resuming", "result_ready")
"""The statuses of a task the worker has not finished with."""


class NewBackgroundTask(BaseModel):
    """The durable call a turn defers, as the row records it.

    ``phase_overrides`` is the deferring turn's per-phase picks, so the turn
    that answers the call resolves the same models.
    """

    model_config = ConfigDict(frozen=True)

    conversation_id: UUID
    user_id: UUID
    tool_name: str
    tool_call_id: str
    args: dict[str, Any]
    estimated_duration_seconds: int
    phase_overrides: dict[str, Any]


class BackgroundTaskRepository:
    """Create + transition ``BackgroundTask`` rows from the worker."""

    def __init__(self, *, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    async def create(self, *, task: NewBackgroundTask) -> UUID:
        task_id = uuid4()
        async with self._session_factory() as session:
            session.add(
                BackgroundTask(
                    id=task_id,
                    status="pending",
                    **task.model_dump(),
                )
            )
            await session.commit()
        return task_id

    async def get(self, *, task_id: UUID) -> BackgroundTask | None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(BackgroundTask).where(BackgroundTask.id == task_id)
            )
            return result.scalar_one_or_none()

    async def list_active_for_conversation(
        self,
        *,
        conversation_id: UUID,
    ) -> list[BackgroundTask]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(BackgroundTask)
                .where(BackgroundTask.conversation_id == conversation_id)
                .where(BackgroundTask.status.in_(ACTIVE_TASK_STATES))
            )
            return list(result.scalars().all())

    async def mark_running(self, *, task_id: UUID) -> None:
        await self._set_values(
            task_id,
            status="running",
            started_at=datetime.now(UTC),
        )

    async def mark_result_ready(self, *, task_id: UUID, result: dict[str, Any]) -> None:
        await self._set_values(
            task_id,
            status="result_ready",
            result=result,
        )

    async def mark_resuming(self, *, task_id: UUID) -> None:
        await self._set_values(task_id, status="resuming")

    async def mark_complete(self, *, task_id: UUID) -> None:
        await self._set_values(
            task_id,
            status="complete",
            completed_at=datetime.now(UTC),
        )
        await self._notify_terminal(task_id=task_id)

    async def mark_failed(self, *, task_id: UUID, error: str) -> None:
        await self._set_values(
            task_id,
            status="failed",
            error=error,
            completed_at=datetime.now(UTC),
        )
        await self._notify_terminal(task_id=task_id)

    async def _set_values(self, task_id: UUID, **values: Any) -> None:
        async with self._session_factory() as session:
            await session.execute(
                update(BackgroundTask)
                .where(BackgroundTask.id == task_id)
                .values(**values)
            )
            await session.commit()

    async def _notify_terminal(self, *, task_id: UUID) -> None:
        """Wake the events-SSE listener by NOTIFYing ``chat_events:<conversation_id>``.

        The SSE endpoint LISTENs on this channel and re-checks the task's
        status after every NOTIFY. Without this wake-up, the stream would
        keep polling on an already-terminal task until the next progress or
        chat event happened to arrive.
        """
        async with self._session_factory() as session:
            row = (
                await session.execute(
                    select(BackgroundTask.conversation_id).where(
                        BackgroundTask.id == task_id
                    )
                )
            ).scalar_one_or_none()
            if row is None:
                return
            await session.execute(
                text("SELECT pg_notify(:channel, :payload)"),
                {
                    "channel": f"chat_events:{row}",
                    "payload": str(task_id),
                },
            )
            await session.commit()
