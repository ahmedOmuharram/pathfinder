from __future__ import annotations

import asyncio
import json
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from assistant_core.persistence.models import Conversation
from assistant_core.platform.db import async_session_factory
from sqlalchemy import select, text

from pathfinder.jobs.progress import TaskProgressEmitter
from pathfinder.persistence.models import BackgroundTask, TaskProgress, User
from pathfinder.persistence.repositories.background_tasks import (
    BackgroundTaskRepository,
)


async def _seed_chat_and_task(
    *, user_id: UUID, conversation_id: UUID, task_id: UUID, tool_name: str = "t"
) -> None:
    async with async_session_factory() as session:
        session.add(
            Conversation(
                id=conversation_id, user_id=user_id, site_id="plasmodb", name=""
            )
        )
        await session.flush()
        session.add(
            BackgroundTask(
                id=task_id,
                conversation_id=conversation_id,
                user_id=user_id,
                tool_name=tool_name,
                status="running",
                args={},
                estimated_duration_seconds=30,
            )
        )
        await session.commit()


def _parse_data_chunks(body: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for line in body.splitlines():
        if not line.startswith("data:"):
            continue
        payload = line[len("data:") :].lstrip()
        if not payload:
            continue
        out.append(json.loads(payload))
    return out


@pytest.mark.asyncio
async def test_sse_returns_404_when_task_missing(
    authed_client: httpx.AsyncClient,
) -> None:
    resp = await authed_client.get(
        f"/api/v1/conversations/{uuid4()}/tasks/{uuid4()}/events"
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_sse_returns_404_for_other_users_task(
    authed_client: httpx.AsyncClient,
    authed_user_id: UUID,
) -> None:
    del authed_user_id
    other_user = uuid4()
    conversation_id = uuid4()
    task_id = uuid4()
    async with async_session_factory() as session:
        session.add(User(id=other_user))
        await session.flush()
        session.add(
            Conversation(
                id=conversation_id, user_id=other_user, site_id="plasmodb", name=""
            )
        )
        await session.flush()
        session.add(
            BackgroundTask(
                id=task_id,
                conversation_id=conversation_id,
                user_id=other_user,
                tool_name="t",
                status="running",
                args={},
                estimated_duration_seconds=30,
            )
        )
        await session.commit()

    resp = await authed_client.get(
        f"/api/v1/conversations/{conversation_id}/tasks/{task_id}/events"
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_sse_replays_past_progress_and_completes(
    authed_client: httpx.AsyncClient,
    authed_user_id: UUID,
    app_notify_dispatcher: Any,
) -> None:
    del app_notify_dispatcher
    conversation_id = uuid4()
    task_id = uuid4()
    await _seed_chat_and_task(
        user_id=authed_user_id, conversation_id=conversation_id, task_id=task_id
    )

    emitter = TaskProgressEmitter(
        task_id=task_id,
        conversation_id=conversation_id,
        session_factory=async_session_factory,
    )
    await emitter.update(percent=0.1, message="starting", data=None)
    await emitter.update(percent=0.25, message="loading data", data={"step": "a"})

    # Flip to terminal state BEFORE the client connects: endpoint must
    # replay all rows, detect terminal status, and close the stream.
    repo = BackgroundTaskRepository(session_factory=async_session_factory)
    await repo.mark_result_ready(task_id=task_id, result={"ok": True})
    await repo.mark_complete(task_id=task_id)

    resp = await authed_client.get(
        f"/api/v1/conversations/{conversation_id}/tasks/{task_id}/events"
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert "x-vercel-ai-ui-message-stream" not in resp.headers

    chunks = _parse_data_chunks(resp.text)
    progress = [
        c
        for c in chunks
        if c.get("type") == "custom" and c.get("kind") == "data-task-progress"
    ]
    completion = [
        c
        for c in chunks
        if c.get("type") == "custom" and c.get("kind") == "data-task-completed"
    ]

    assert len(progress) == 2, progress
    assert progress[0]["data"]["message"] == "starting"
    assert progress[1]["data"]["message"] == "loading data"
    percents = [p["data"]["percent"] for p in progress]
    assert percents == sorted(percents), (
        f"past progress must replay in id order, got {percents}"
    )
    assert completion, completion
    assert completion[-1]["data"]["status"] == "success"
    assert completion[-1]["data"]["taskId"] == str(task_id)


@pytest.mark.asyncio
async def test_sse_receives_past_and_live_progress(
    authed_client: httpx.AsyncClient,
    authed_user_id: UUID,
    app_notify_dispatcher: Any,
) -> None:
    del app_notify_dispatcher
    conversation_id = uuid4()
    task_id = uuid4()
    await _seed_chat_and_task(
        user_id=authed_user_id, conversation_id=conversation_id, task_id=task_id
    )

    emitter = TaskProgressEmitter(
        task_id=task_id,
        conversation_id=conversation_id,
        session_factory=async_session_factory,
    )
    # One row is persisted BEFORE the client connects — must replay.
    await emitter.update(percent=0.1, message="starting", data=None)

    repo = BackgroundTaskRepository(session_factory=async_session_factory)

    async def producer() -> None:
        # Give the endpoint time to open the LISTEN before we NOTIFY, so the
        # "halfway" row is delivered via pg_notify (not replay).
        await asyncio.sleep(0.3)
        await emitter.update(percent=0.5, message="halfway", data=None)
        await asyncio.sleep(0.1)
        await repo.mark_result_ready(task_id=task_id, result={"ok": True})
        await repo.mark_complete(task_id=task_id)

    producer_task = asyncio.create_task(producer())
    resp = await authed_client.get(
        f"/api/v1/conversations/{conversation_id}/tasks/{task_id}/events"
    )
    await producer_task

    assert resp.status_code == 200
    chunks = _parse_data_chunks(resp.text)
    messages = [
        c["data"]["message"]
        for c in chunks
        if c.get("type") == "custom" and c.get("kind") == "data-task-progress"
    ]
    assert "starting" in messages, f"past progress missing: {messages}"
    assert "halfway" in messages, f"live progress missing: {messages}"
    completion = [
        c
        for c in chunks
        if c.get("type") == "custom" and c.get("kind") == "data-task-completed"
    ]
    assert completion, completion
    assert completion[-1]["data"]["status"] == "success"


@pytest.mark.asyncio
async def test_sse_emits_task_completed_when_task_failed(
    authed_client: httpx.AsyncClient,
    authed_user_id: UUID,
    app_notify_dispatcher: Any,
) -> None:
    del app_notify_dispatcher
    conversation_id = uuid4()
    task_id = uuid4()
    await _seed_chat_and_task(
        user_id=authed_user_id, conversation_id=conversation_id, task_id=task_id
    )

    repo = BackgroundTaskRepository(session_factory=async_session_factory)
    await repo.mark_failed(task_id=task_id, error="boom")

    resp = await authed_client.get(
        f"/api/v1/conversations/{conversation_id}/tasks/{task_id}/events"
    )
    assert resp.status_code == 200
    chunks = _parse_data_chunks(resp.text)
    completion = [
        c
        for c in chunks
        if c.get("type") == "custom" and c.get("kind") == "data-task-completed"
    ]
    assert completion, chunks
    assert completion[-1]["data"]["status"] == "failed"
    assert completion[-1]["data"]["error"] == "boom"


@pytest.mark.asyncio
async def test_task_status_returns_current_state(
    authed_client: httpx.AsyncClient,
    authed_user_id: UUID,
) -> None:
    conversation_id = uuid4()
    task_id = uuid4()
    await _seed_chat_and_task(
        user_id=authed_user_id,
        conversation_id=conversation_id,
        task_id=task_id,
        tool_name="run_control_tests_on_step",
    )
    repo = BackgroundTaskRepository(session_factory=async_session_factory)
    await repo.mark_result_ready(task_id=task_id, result={"ok": True})
    await repo.mark_complete(task_id=task_id)

    resp = await authed_client.get(
        f"/api/v1/conversations/{conversation_id}/tasks/{task_id}"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["taskId"] == str(task_id)
    assert body["toolName"] == "run_control_tests_on_step"
    assert body["status"] == "complete"
    assert body["result"] == {"ok": True}
    assert body["estimatedDurationSeconds"] == 30
    assert body["completedAt"] is not None


@pytest.mark.asyncio
async def test_task_status_returns_404_when_missing(
    authed_client: httpx.AsyncClient,
) -> None:
    resp = await authed_client.get(f"/api/v1/conversations/{uuid4()}/tasks/{uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_task_progress_history_returns_rows_in_order(
    authed_client: httpx.AsyncClient,
    authed_user_id: UUID,
) -> None:
    conversation_id = uuid4()
    task_id = uuid4()
    await _seed_chat_and_task(
        user_id=authed_user_id, conversation_id=conversation_id, task_id=task_id
    )
    emitter = TaskProgressEmitter(
        task_id=task_id,
        conversation_id=conversation_id,
        session_factory=async_session_factory,
    )
    await emitter.update(percent=0.1, message="a", data=None)
    await emitter.update(percent=0.5, message="b", data={"k": "v"})
    await emitter.update(percent=0.9, message="c", data=None)

    resp = await authed_client.get(
        f"/api/v1/conversations/{conversation_id}/tasks/{task_id}/progress"
    )
    assert resp.status_code == 200
    rows = resp.json()
    assert [r["message"] for r in rows] == ["a", "b", "c"]
    assert [r["percent"] for r in rows] == [0.1, 0.5, 0.9]
    assert rows[1]["data"] == {"k": "v"}
    assert all(r["taskId"] == str(task_id) for r in rows)


@pytest.mark.asyncio
async def test_task_progress_history_returns_404_when_missing(
    authed_client: httpx.AsyncClient,
) -> None:
    resp = await authed_client.get(
        f"/api/v1/conversations/{uuid4()}/tasks/{uuid4()}/progress"
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_live_stream_emits_progress_and_terminal_when_batched(
    authed_client: httpx.AsyncClient,
    authed_user_id: UUID,
    app_notify_dispatcher: Any,
) -> None:
    """Live SSE must yield trailing progress rows when the terminal flip
    lands in the same commit.

    The completion turn's chunks go to the main chat stream
    (:func:`pathfinder.jobs.runner._run_completion_turn` via
    :class:`ChatEventWriter`), so this endpoint only carries
    ``data-task-progress`` + the terminal ``data-task-completed`` chunk.
    """
    del app_notify_dispatcher
    conversation_id = uuid4()
    task_id = uuid4()
    await _seed_chat_and_task(
        user_id=authed_user_id, conversation_id=conversation_id, task_id=task_id
    )

    async def producer() -> None:
        # Let the endpoint subscribe, finish replay, and park in _poll_loop
        # before the writes commit.
        await asyncio.sleep(0.3)
        async with async_session_factory() as session:
            session.add(
                TaskProgress(
                    task_id=task_id,
                    percent=1.0,
                    message="final",
                    data=None,
                ),
            )
            await session.flush()
            await session.execute(
                text("SELECT pg_notify(:channel, :payload)"),
                {
                    "channel": f"task_progress:{conversation_id}",
                    "payload": str(task_id),
                },
            )
            task_row = (
                await session.execute(
                    select(BackgroundTask).where(
                        BackgroundTask.id == task_id,
                    ),
                )
            ).scalar_one()
            task_row.status = "complete"
            await session.commit()

    producer_task = asyncio.create_task(producer())
    resp = await authed_client.get(
        f"/api/v1/conversations/{conversation_id}/tasks/{task_id}/events"
    )
    await producer_task

    assert resp.status_code == 200
    progress_messages = [
        c["data"]["message"]
        for c in _parse_data_chunks(resp.text)
        if c.get("type") == "custom" and c.get("kind") == "data-task-progress"
    ]
    assert "final" in progress_messages, progress_messages
    completion = [
        c
        for c in _parse_data_chunks(resp.text)
        if c.get("type") == "custom" and c.get("kind") == "data-task-completed"
    ]
    assert completion, resp.text
    assert completion[-1]["data"]["status"] == "success"
