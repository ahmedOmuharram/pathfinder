"""Durable-task progress emission (worker-side).

The worker emits incremental progress for a durable task: it persists rows
to ``task_progress`` and fires a ``pg_notify`` on
``task_progress:<conversation_id>`` so the dispatcher can stream progress
into the UI without polling.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from assistant_core.platform.db import DBSessionFactory
from sqlalchemy import text

from pathfinder.persistence.models import TaskProgress


@dataclass(frozen=True)
class _PendingProgress:
    percent: float
    message: str
    data: dict[str, Any] | None


@dataclass
class TaskProgressEmitter:
    """Records a durable task's incremental progress.

    By default (``batch_size=1``), each :meth:`update` commits immediately
    and fires one ``pg_notify``. Callers that emit many rows rapidly can opt
    in to batching via ``batch_size > 1``: rows buffer in memory and flush
    when the buffer fills, when :attr:`max_flush_interval_seconds` elapses,
    or on explicit :meth:`flush` / :meth:`aclose`.

    Use :meth:`scoped` to derive a child emitter that tags every ``data``
    payload with a fixed scope dict (e.g. ``variantId="v3"`` for fan-out).
    """

    task_id: UUID
    conversation_id: UUID
    session_factory: DBSessionFactory
    batch_size: int = 1
    max_flush_interval_seconds: float = 1.0
    _scope_data: dict[str, Any] = field(default_factory=dict)
    _buffer: list[_PendingProgress] = field(default_factory=list)
    _last_flush_monotonic: float = field(default=0.0)

    def scoped(self, **scope: Any) -> TaskProgressEmitter:
        """Return a child emitter that tags every update with ``scope``."""
        child = TaskProgressEmitter(
            task_id=self.task_id,
            conversation_id=self.conversation_id,
            session_factory=self.session_factory,
            batch_size=self.batch_size,
            max_flush_interval_seconds=self.max_flush_interval_seconds,
        )
        child._scope_data = {**self._scope_data, **scope}
        return child

    async def update(
        self,
        *,
        percent: float,
        message: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        merged: dict[str, Any] | None
        if self._scope_data or data is not None:
            merged = {**self._scope_data, **(data or {})}
        else:
            merged = None
        self._buffer.append(
            _PendingProgress(percent=percent, message=message, data=merged),
        )
        now = time.monotonic()
        if self._last_flush_monotonic == 0.0:
            self._last_flush_monotonic = now
        should_flush = (
            len(self._buffer) >= self.batch_size
            or (now - self._last_flush_monotonic) >= self.max_flush_interval_seconds
        )
        if should_flush:
            await self.flush()

    async def flush(self) -> None:
        """Commit all buffered rows + fire one NOTIFY. No-op if empty."""
        if not self._buffer:
            return
        pending = list(self._buffer)
        self._buffer.clear()
        async with self.session_factory() as session:
            session.add_all(
                TaskProgress(
                    task_id=self.task_id,
                    percent=row.percent,
                    message=row.message,
                    data=row.data,
                )
                for row in pending
            )
            await session.flush()
            await session.execute(
                text("SELECT pg_notify(:channel, :payload)"),
                {
                    "channel": f"task_progress:{self.conversation_id}",
                    "payload": str(self.task_id),
                },
            )
            await session.commit()
        self._last_flush_monotonic = time.monotonic()

    async def aclose(self) -> None:
        await self.flush()
