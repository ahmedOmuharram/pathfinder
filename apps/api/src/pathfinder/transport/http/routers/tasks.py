"""HTTP endpoints for durable task status, progress history, and the progress SSE stream."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from assistant_core.platform.pydantic_base import CamelModel
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from shared_py.stream_events import CustomEvent, DoneEvent, StreamEvent

from pathfinder.platform.notify_dispatcher import NotifyDispatcher
from pathfinder.platform.security import get_current_user
from pathfinder.services.tasks.queries import (
    ProgressRow,
    latest_progress_by_task,
    list_task_rows,
    load_task,
    progress_rows,
    terminal_status,
)
from pathfinder.transport.http.schemas.tasks import (
    TaskListItem,
    TaskListResponse,
    TaskProgressEvent,
    TaskStatusResponse,
)

router = APIRouter(prefix="/api/v1/conversations", tags=["tasks"])

_NOTIFY_POLL_TIMEOUT_SECONDS: float = 1.0


def _encode_event(event: StreamEvent) -> str:
    return f"event: stream\ndata: {event.model_dump_json(by_alias=True)}\n\n"


class _Cursor(CamelModel):
    last_progress_id: int = 0


@router.get("/{conversation_id}/tasks", response_model=TaskListResponse)
async def list_tasks(
    conversation_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user)],
    status_in: Annotated[
        str | None,
        Query(
            alias="status",
            description=(
                "Comma-separated status filter "
                "(pending, running, resuming, complete, failed)"
            ),
        ),
    ] = None,
) -> TaskListResponse:
    """Return durable tasks for a conversation, newest first."""
    statuses: set[str] | None = None
    if status_in:
        statuses = {s.strip() for s in status_in.split(",") if s.strip()}
    tasks = await list_task_rows(
        conversation_id=conversation_id,
        user_id=user_id,
        statuses=statuses,
    )
    latest = await latest_progress_by_task([t.id for t in tasks])
    items = [
        TaskListItem(
            task_id=task.id,
            tool_name=task.tool_name,
            status=task.status,
            estimated_duration_seconds=task.estimated_duration_seconds,
            created_at=task.created_at,
            started_at=task.started_at,
            completed_at=task.completed_at,
            latest_percent=latest[task.id].percent if task.id in latest else None,
            latest_message=latest[task.id].message if task.id in latest else None,
            error=task.error,
        )
        for task in tasks
    ]
    return TaskListResponse(tasks=items)


@router.get("/{conversation_id}/tasks/{task_id}", response_model=TaskStatusResponse)
async def task_status(
    conversation_id: UUID,
    task_id: UUID,
    user_id: Annotated[UUID, Depends(get_current_user)],
) -> TaskStatusResponse:
    """Return current status + metadata for a durable task."""
    task = await load_task(
        conversation_id=conversation_id,
        task_id=task_id,
        user_id=user_id,
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
    await load_task(conversation_id=conversation_id, task_id=task_id, user_id=user_id)
    return [
        TaskProgressEvent(
            task_id=task_id,
            percent=row.percent,
            message=row.message,
            data=row.data,
            emitted_at=row.emitted_at,
        )
        for row in await progress_rows(task_id)
    ]


@router.get("/{conversation_id}/tasks/{task_id}/events")
async def task_events(
    conversation_id: UUID,
    task_id: UUID,
    request: Request,
    user_id: Annotated[UUID, Depends(get_current_user)],
) -> StreamingResponse:
    """Open an SSE stream for a durable task's progress."""
    await load_task(conversation_id=conversation_id, task_id=task_id, user_id=user_id)
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


def _progress_chunk(task_id: UUID, row: ProgressRow) -> CustomEvent:
    return CustomEvent(
        kind="data-task-progress",
        data={
            "taskId": str(task_id),
            "percent": row.percent,
            "message": row.message,
            "toolSpecific": row.data,
        },
    )


def _completed_chunk(task_id: UUID, status: str, error: str | None) -> CustomEvent:
    return CustomEvent(
        kind="data-task-completed",
        data={
            "taskId": str(task_id),
            "status": "success" if status == "complete" else "failed",
            "error": error,
        },
    )


async def _event_stream(
    *,
    conversation_id: UUID,
    task_id: UUID,
    request: Request,
    dispatcher: NotifyDispatcher,
) -> AsyncIterator[str]:
    """Stream task progress. Subscription opens before the first query, so no notification is lost."""
    progress_channel = f"task_progress:{conversation_id}"
    encountered_error = False
    try:
        cursor = _Cursor()
        async with dispatcher.subscribe(
            frozenset({progress_channel}),
        ) as notify_queue:
            async for frame in _drain(task_id, cursor):
                yield frame
            terminal = await _terminal_chunk_if_done(task_id)
            if terminal is not None:
                yield _encode_event(terminal)
                return
            async for frame in _poll_loop(
                notify_queue=notify_queue,
                task_id=task_id,
                cursor=cursor,
                request=request,
            ):
                yield frame
    except Exception:
        encountered_error = True
        raise
    finally:
        yield _encode_event(
            DoneEvent(reason="error" if encountered_error else "completed"),
        )


async def _drain(task_id: UUID, cursor: _Cursor) -> AsyncIterator[str]:
    for row in await progress_rows(task_id, after_id=cursor.last_progress_id):
        cursor.last_progress_id = max(cursor.last_progress_id, row.id)
        yield _encode_event(_progress_chunk(task_id, row))


async def _poll_loop(
    *,
    notify_queue: asyncio.Queue[tuple[str, str]],
    task_id: UUID,
    cursor: _Cursor,
    request: Request,
) -> AsyncIterator[str]:
    """Drain NOTIFYs from the dispatcher queue until terminal or disconnect."""
    while True:
        if await request.is_disconnected():
            return
        await _wait_for_notify(notify_queue)
        async for frame in _drain(task_id, cursor):
            yield frame
        terminal = await _terminal_chunk_if_done(task_id)
        if terminal is not None:
            yield _encode_event(terminal)
            return


async def _wait_for_notify(notify_queue: asyncio.Queue[tuple[str, str]]) -> None:
    """Wake on any notification or on the poll timeout. The channel name is ignored."""
    try:
        await asyncio.wait_for(
            notify_queue.get(),
            timeout=_NOTIFY_POLL_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        return


async def _terminal_chunk_if_done(task_id: UUID) -> CustomEvent | None:
    terminal = await terminal_status(task_id)
    if terminal is None:
        return None
    status, error = terminal
    return _completed_chunk(task_id, status, error)
