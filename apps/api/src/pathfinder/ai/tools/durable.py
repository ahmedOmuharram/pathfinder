"""Primitives for durable (long-running) agent tools.

Durable tools dispatch their work to the Procrastinate worker and stream
progress back to the chat via ``TaskProgressEmitter``. The emitter persists
rows to ``task_progress`` and publishes a LISTEN/NOTIFY event on
``task_progress:<conversation_id>`` so the dispatcher can resume/flush progress into
the UI message stream without polling.

``@durable_tool`` wraps an agent-side tool so calling it submits a
Procrastinate job and then ``interrupt()``s the graph. The real work runs on
the worker via the ``TOOL_REGISTRY`` mapping.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, ParamSpec, TypeVar, cast
from uuid import UUID

from langgraph.config import get_stream_writer
from langgraph.types import interrupt
from pydantic import TypeAdapter
from pydantic_ai.tools import RunContext
from pydantic_ai.ui.vercel_ai.response_types import BaseChunk
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.jobs.app import procrastinate_app
from pathfinder.jobs.payloads import DurableTaskPayload
from pathfinder.persistence.models import TaskProgress
from pathfinder.persistence.repositories.background_tasks import (
    BackgroundTaskRepository,
)
from pathfinder.persistence.session import async_session_factory

SessionFactory = Callable[[], AsyncSession]

P = ParamSpec("P")
R = TypeVar("R")


@dataclass(frozen=True)
class _PendingProgress:
    percent: float
    message: str
    data: dict[str, Any] | None


@dataclass
class TaskProgressEmitter:
    """Records a durable task's incremental progress.

    By default (``batch_size=1``), each :meth:`update` commits immediately
    and fires one ``pg_notify`` — same semantics as the original
    implementation, safe for tests and low-frequency progress. Callers
    that emit many rows rapidly (e.g. :mod:`optimize_params_impl` with
    30 trials) can opt in to batching by passing ``batch_size > 1`` at
    construction: rows buffer in memory and flush when the buffer fills,
    when :attr:`max_flush_interval_seconds` elapses, or on explicit
    :meth:`flush` / :meth:`aclose`. :meth:`aclose` is called by the
    runner at task completion so no rows are ever dropped.

    Batched flushes insert N rows in a single ``session.add_all`` and
    fire ONE NOTIFY per batch — O(batches) DB round-trips instead of
    O(rows).

    Use :meth:`scoped` to derive a child emitter that tags every
    ``data`` payload with a fixed scope dict (e.g. ``variantId="v3"`` for
    parameter-sweep fan-out). Children share the parent's persistence
    plumbing but maintain their own buffer and merged scope.
    """

    task_id: UUID
    conversation_id: UUID
    session_factory: SessionFactory
    batch_size: int = 1
    max_flush_interval_seconds: float = 1.0
    _scope_data: dict[str, Any] = field(default_factory=dict)
    _buffer: list[_PendingProgress] = field(default_factory=list)
    _last_flush_monotonic: float = field(default=0.0)

    def scoped(self, **scope: Any) -> TaskProgressEmitter:
        """Return a child emitter that tags every update with ``scope``.

        The child shares persistence config (session_factory, task_id,
        conversation_id, batch_size) with this emitter but holds its own buffer
        + scope. Each ``update`` on the child merges the scope dict into
        its ``data`` field before persisting.
        """
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
            or (now - self._last_flush_monotonic)
            >= self.max_flush_interval_seconds
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


ChunkBuilder = Callable[[Any, UUID], list[BaseChunk]]


def durable_tool(
    *,
    tool_name: str,
    estimated_duration_seconds: int,
    chunks_from_result: ChunkBuilder | None = None,
) -> Callable[
    [Callable[P, Awaitable[R]]],
    Callable[P, Awaitable[R]],
]:
    """Mark an agent-side pydantic-ai tool as durable.

    ``chunks_from_result`` lets a tool emit chat-visible SSE chunks built
    from the resumed payload — runs at resume time inside the LangGraph
    node, so chunks are persisted/replayed via the same writer as the
    agent's own stream output.
    """

    def decorator(
        fn: Callable[P, Awaitable[R]],
    ) -> Callable[P, Awaitable[R]]:
        @wraps(fn)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            ctx, tool_args = _parse_invocation(args, kwargs)
            deps = _require_durable_deps(ctx.deps)

            repo = BackgroundTaskRepository(session_factory=async_session_factory)
            task_id = await repo.create(
                conversation_id=deps.conversation_id,
                user_id=deps.user_id,
                tool_name=tool_name,
                args=tool_args,
                estimated_duration_seconds=estimated_duration_seconds,
            )
            task = procrastinate_app.configure_task(
                name=f"durable:{tool_name}",
                queue="verification",
            )
            dispatched_payload = DurableTaskPayload.from_context(
                task_id=task_id,
                thread_id=deps.conversation_id,
                args=tool_args,
            )
            await task.defer_async(
                **dispatched_payload.model_dump(mode="json", by_alias=True),
            )

            resumed = interrupt(
                {
                    "kind": "durable_task",
                    "task_id": str(task_id),
                    "tool_name": tool_name,
                    "estimated_duration_seconds": estimated_duration_seconds,
                }
            )
            if chunks_from_result is not None:
                writer = get_stream_writer()
                for chunk in chunks_from_result(resumed, task_id):
                    writer(
                        {
                            "chunk": chunk.model_dump(
                                by_alias=True, mode="json", exclude_none=True,
                            ),
                        },
                    )
            return cast("R", resumed)

        return wrapper

    return decorator


@dataclass(frozen=True)
class _DurableDeps:
    """AgentDeps subset required for durable dispatch."""

    conversation_id: UUID
    user_id: UUID


def _require_durable_deps(deps: AgentDeps) -> _DurableDeps:
    if deps.conversation_id is None:
        msg = "durable_tool requires conversation_id on AgentDeps"
        raise RuntimeError(msg)
    if deps.user_id is None:
        msg = "durable_tool requires user_id on AgentDeps"
        raise RuntimeError(msg)
    return _DurableDeps(conversation_id=deps.conversation_id, user_id=deps.user_id)


def _parse_invocation(
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> tuple[RunContext[AgentDeps], dict[str, Any]]:
    if not args:
        msg = "durable_tool requires RunContext[AgentDeps] as first argument"
        raise RuntimeError(msg)
    ctx = cast("RunContext[AgentDeps]", args[0])
    tool_args: dict[str, Any] = {
        "args": [_to_jsonable(v) for v in args[1:]],
        "kwargs": {k: _to_jsonable(v) for k, v in kwargs.items()},
    }
    return ctx, tool_args


_ANY_JSON: TypeAdapter[Any] = TypeAdapter(Any)


def _to_jsonable(value: Any) -> Any:
    return _ANY_JSON.dump_python(value, mode="json")
