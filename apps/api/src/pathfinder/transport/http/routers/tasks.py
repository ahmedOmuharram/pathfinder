"""Task events SSE endpoint.

Streams durable-task progress and resumed-graph chunks to the client as
``text/event-stream`` frames. Replays existing ``task_progress`` +
``chat_events`` rows on connect, then subscribes to two Postgres channels
(``task_progress:<conversation_id>`` and ``chat_events:<conversation_id>``) via
``LISTEN/NOTIFY`` so new rows land in the stream as soon as they are written.

Frame format mirrors the chat dispatcher: every frame is
``event: stream\\ndata: {camelCase StreamEvent JSON}\\n\\n``. The terminal
marker is a typed :class:`shared_py.stream_events.DoneEvent`; clients filter
on ``event: stream`` and dispatch on the typed payload's ``type``
discriminator.

Ordering: we track ``last_progress_id`` and ``last_event_id`` across the
replay + NOTIFY loop. Every NOTIFY triggers ``WHERE id > :last`` queries that
yield the full batch of unseen rows in id order, so no rows are duplicated
or dropped even when multiple writes arrive between notifications.

Termination: the loop exits when the ``BackgroundTask`` row reaches the
terminal ``complete`` or ``failed`` status (emitting a final
``data-task-completed`` chunk + a typed ``DoneEvent``), when the client
disconnects, or when the long poll on ``notifies()`` is cancelled.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from shared_py.stream_events import CustomEvent, DoneEvent, StreamEvent
from sqlalchemy import select

from pathfinder.persistence.models import (
    BackgroundTask,
    ConversationEvent,
    TaskProgress,
)
from pathfinder.persistence.session import async_session_factory
from pathfinder.platform.notify_dispatcher import NotifyDispatcher
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.platform.security import get_current_user
from pathfinder.transport.http.schemas.tasks import (
    TaskProgressEvent,
    TaskStatusResponse,
)

router = APIRouter(prefix="/api/v1/conversations", tags=["tasks"])

# Polling timeout on ``aconn.notifies()``. Short enough to check
# ``request.is_disconnected()`` responsively; long enough to avoid busy-looping.
_NOTIFY_POLL_TIMEOUT_SECONDS: float = 1.0
_TERMINAL_TASK_STATUSES: frozenset[str] = frozenset({"complete", "failed"})


def _encode_event(event: StreamEvent) -> str:
    return (
        f"event: stream\n"
        f"data: {event.model_dump_json(by_alias=True)}\n\n"
    )


class _Cursor(CamelModel):
    """Monotonic cursor across ``task_progress`` + ``chat_events``.

    We track the largest id seen on each channel so that after every NOTIFY we
    can fetch the strictly-newer rows in one query, in id order, with no
    duplicates and no drops.
    """

    last_progress_id: int = 0
    last_event_id: int = 0


@router.get(
    "/{conversation_id}/tasks/{task_id}",
    response_model=TaskStatusResponse,
)
async def task_status(
    conversation_id: UUID,
    task_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user)],
) -> TaskStatusResponse:
    """Return current status + metadata for a durable task."""
    task = await _load_task(
        conversation_id=conversation_id, task_id=task_id, user_id=user_id
    )
    return TaskStatusResponse(
        task_id=task.id,
        tool_name=task.tool_name,
        status=task.status,
        estimated_duration_seconds=task.estimated_duration_seconds,
        started_at=task.started_at,
        completed_at=task.completed_at,
        result=task.result,
        error=task.error,
    )


@router.get(
    "/{conversation_id}/tasks/{task_id}/progress",
    response_model=list[TaskProgressEvent],
)
async def task_progress_history(
    conversation_id: UUID,
    task_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user)],
) -> list[TaskProgressEvent]:
    """Return the ordered list of progress rows persisted so far."""
    await _load_task(conversation_id=conversation_id, task_id=task_id, user_id=user_id)
    async with async_session_factory() as session:
        rows = (
            await session.execute(
                select(TaskProgress)
                .where(TaskProgress.task_id == task_id)
                .order_by(TaskProgress.id)
            )
        ).scalars().all()
    return [
        TaskProgressEvent(
            task_id=task_id,
            percent=row.percent,
            message=row.message,
            data=row.data,
            emitted_at=row.emitted_at,
        )
        for row in rows
    ]


@router.get("/{conversation_id}/tasks/{task_id}/events")
async def task_events(
    conversation_id: UUID,
    task_id: UUID,
    request: Request,
    user_id: Annotated[UUID, Depends(get_current_user)],
) -> StreamingResponse:
    """Open an SSE stream for a durable task's progress + resumed graph output."""
    await _load_task(conversation_id=conversation_id, task_id=task_id, user_id=user_id)
    dispatcher: NotifyDispatcher = request.app.state.notify_dispatcher

    return StreamingResponse(
        _event_stream(
            conversation_id=conversation_id,
            task_id=task_id,
            request=request,
            dispatcher=dispatcher,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


async def _load_task(
    *, conversation_id: UUID, task_id: UUID, user_id: UUID
) -> BackgroundTask:
    async with async_session_factory() as session:
        task = (
            await session.execute(
                select(BackgroundTask).where(
                    BackgroundTask.id == task_id,
                    BackgroundTask.conversation_id == conversation_id,
                    BackgroundTask.user_id == user_id,
                )
            )
        ).scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    return task


def _progress_chunk(task_id: UUID, row: TaskProgress) -> CustomEvent:
    return CustomEvent(
        kind="data-task-progress",
        data={
            "taskId": str(task_id),
            "percent": row.percent,
            "message": row.message,
            "toolSpecific": row.data,
        },
    )


def _completed_chunk(
    task_id: UUID, status: str, error: str | None
) -> CustomEvent:
    return CustomEvent(
        kind="data-task-completed",
        data={
            "taskId": str(task_id),
            "status": "success" if status == "complete" else "failed",
            "error": error,
        },
    )


class _ChatEventChunk(CamelModel):
    """Shape persisted in ``chat_events.chunk`` by ``jobs/runner._persist_chat_event``.

    Validating on read catches any schema drift — if a different producer
    starts writing a different shape, we log a warning instead of silently
    dropping the row.
    """

    sse: str


def _extract_sse_line(chunk: dict[str, Any]) -> str | None:
    try:
        parsed = _ChatEventChunk.model_validate(chunk)
    except ValueError:
        return None
    return parsed.sse


async def _event_stream(
    *,
    conversation_id: UUID,
    task_id: UUID,
    request: Request,
    dispatcher: NotifyDispatcher,
) -> AsyncIterator[str]:
    """Subscribe BEFORE querying so no NOTIFY can be lost.

    Subscriptions go through the process-wide :class:`NotifyDispatcher` so
    every SSE client shares a single Postgres backend instead of opening
    its own. The dispatcher holds LISTEN from the moment ``subscribe()``
    returns, so any NOTIFY fired after that is queued for delivery — even
    ones that race with the replay and terminal check below.
    """
    progress_channel = f"task_progress:{conversation_id}"
    events_channel = f"chat_events:{conversation_id}"
    encountered_error = False
    try:
        cursor = _Cursor()
        async with dispatcher.subscribe(
            frozenset({progress_channel, events_channel}),
        ) as notify_queue:
            async for frame in _replay(
                conversation_id=conversation_id, task_id=task_id, cursor=cursor,
            ):
                yield frame

            terminal = await _terminal_chunk_if_done(task_id)
            if terminal is not None:
                yield _encode_event(terminal)
                return

            async for frame in _poll_loop(
                notify_queue=notify_queue,
                target=_PollTarget(
                    conversation_id=conversation_id, task_id=task_id,
                    progress_channel=progress_channel,
                    events_channel=events_channel,
                ),
                cursor=cursor,
                request=request,
            ):
                yield frame
    except Exception:
        encountered_error = True
        raise
    finally:
        yield _encode_event(
            DoneEvent(reason="error" if encountered_error else "completed")
        )


async def _replay(
    *, conversation_id: UUID, task_id: UUID, cursor: _Cursor
) -> AsyncIterator[str]:
    async with async_session_factory() as session:
        progress_rows = (
            await session.execute(
                select(TaskProgress)
                .where(TaskProgress.task_id == task_id)
                .order_by(TaskProgress.id)
            )
        ).scalars().all()
        for progress_row in progress_rows:
            cursor.last_progress_id = max(
                cursor.last_progress_id, progress_row.id
            )
            yield _encode_event(_progress_chunk(task_id, progress_row))

        event_rows = (
            await session.execute(
                select(ConversationEvent)
                .where(
                    ConversationEvent.conversation_id == conversation_id,
                    ConversationEvent.task_id == task_id,
                )
                .order_by(ConversationEvent.id)
            )
        ).scalars().all()
        for event_row in event_rows:
            cursor.last_event_id = max(cursor.last_event_id, event_row.id)
            line = _extract_sse_line(event_row.chunk)
            if line is not None:
                yield line


@dataclass(frozen=True)
class _PollTarget:
    conversation_id: UUID
    task_id: UUID
    progress_channel: str
    events_channel: str


async def _poll_loop(
    *,
    notify_queue: asyncio.Queue[tuple[str, str]],
    target: _PollTarget,
    cursor: _Cursor,
    request: Request,
) -> AsyncIterator[str]:
    """Drain NOTIFYs from the dispatcher queue until terminal or disconnect."""
    while True:
        if await request.is_disconnected():
            return

        await _wait_for_notify(notify_queue)
        async for frame in _drain_both_tables(target, cursor):
            yield frame

        terminal = await _terminal_chunk_if_done(target.task_id)
        if terminal is not None:
            yield _encode_event(terminal)
            return


async def _wait_for_notify(
    notify_queue: asyncio.Queue[tuple[str, str]],
) -> None:
    """Wake up on any NOTIFY or on poll-timeout. Channel is ignored.

    Both tables are drained unconditionally every iteration, so which
    channel fired is irrelevant — we only need the wake-up signal.
    """
    try:
        await asyncio.wait_for(
            notify_queue.get(), timeout=_NOTIFY_POLL_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        return


async def _drain_both_tables(
    target: _PollTarget,
    cursor: _Cursor,
) -> AsyncIterator[str]:
    """Drain progress + events unconditionally.

    Filtering by notified channel used to drop trailing rows whenever a
    progress NOTIFY and an events NOTIFY both arrived before the terminal
    flip: the progress iteration drained only progress, the terminal check
    fired, and the queued events NOTIFY (with its unread row) was
    discarded. Draining both every iteration is cheap — each query is
    ``WHERE id > :cursor`` with no rows to return on the no-op side — and
    closes the race entirely.
    """
    async for frame in _drain_progress(target.task_id, cursor):
        yield frame
    async for frame in _drain_events(
        target.conversation_id, target.task_id, cursor,
    ):
        yield frame


async def _drain_progress(
    task_id: UUID, cursor: _Cursor
) -> AsyncIterator[str]:
    async with async_session_factory() as session:
        rows = (
            await session.execute(
                select(TaskProgress)
                .where(
                    TaskProgress.task_id == task_id,
                    TaskProgress.id > cursor.last_progress_id,
                )
                .order_by(TaskProgress.id)
            )
        ).scalars().all()
    for row in rows:
        cursor.last_progress_id = row.id
        yield _encode_event(_progress_chunk(task_id, row))


async def _drain_events(
    conversation_id: UUID, task_id: UUID, cursor: _Cursor
) -> AsyncIterator[str]:
    async with async_session_factory() as session:
        rows = (
            await session.execute(
                select(ConversationEvent)
                .where(
                    ConversationEvent.conversation_id == conversation_id,
                    ConversationEvent.task_id == task_id,
                    ConversationEvent.id > cursor.last_event_id,
                )
                .order_by(ConversationEvent.id)
            )
        ).scalars().all()
    for row in rows:
        cursor.last_event_id = row.id
        line = _extract_sse_line(row.chunk)
        if line is not None:
            yield line


async def _terminal_chunk_if_done(task_id: UUID) -> CustomEvent | None:
    async with async_session_factory() as session:
        task = (
            await session.execute(
                select(BackgroundTask).where(BackgroundTask.id == task_id)
            )
        ).scalar_one_or_none()
    if task is None or task.status not in _TERMINAL_TASK_STATUSES:
        return None
    return _completed_chunk(task_id, task.status, task.error)
