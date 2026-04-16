from __future__ import annotations

import asyncio
import json
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest

from pathfinder.ai.tools.durable import TaskProgressEmitter
from pathfinder.persistence.models import BackgroundTask, Chat
from pathfinder.persistence.repositories.background_tasks import (
    BackgroundTaskRepository,
)
from pathfinder.persistence.session import async_session_factory


async def _seed_chat_and_task(
    *, user_id: UUID, chat_id: UUID, task_id: UUID
) -> None:
    async with async_session_factory() as session:
        session.add(Chat(id=chat_id, user_id=user_id, site_id="plasmodb", name=""))
        await session.flush()
        session.add(
            BackgroundTask(
                id=task_id,
                chat_id=chat_id,
                user_id=user_id,
                tool_name="t",
                status="running",
                args={},
                estimated_duration_seconds=30,
            )
        )
        await session.commit()


def _parse_progress(body: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for line in body.splitlines():
        if not line.startswith("data:"):
            continue
        payload = line[len("data:") :].lstrip()
        if not payload:
            continue
        chunk = json.loads(payload)
        if (
            chunk.get("type") == "custom"
            and chunk.get("kind") == "data-task-progress"
        ):
            out.append(chunk)
    return out


@pytest.mark.asyncio
async def test_rapid_fire_progress_arrive_in_order_no_duplicates_no_missing(
    authed_client: httpx.AsyncClient,
    authed_user_id: UUID,
    app_notify_dispatcher: Any,
) -> None:
    del app_notify_dispatcher
    """Five rapid-fire progress.update calls must appear in exact id order,
    with no duplicates and no drops, even under NOTIFY coalescing.

    PostgreSQL coalesces identical pg_notify payloads within a transaction;
    the SSE endpoint MUST track ``last_progress_id`` as a monotonic cursor so
    each NOTIFY causes a ``WHERE id > :last`` query that fetches the full
    batch of newly-written rows.
    """
    chat_id = uuid4()
    task_id = uuid4()
    await _seed_chat_and_task(
        user_id=authed_user_id, chat_id=chat_id, task_id=task_id
    )

    emitter = TaskProgressEmitter(
        task_id=task_id, chat_id=chat_id, session_factory=async_session_factory
    )
    repo = BackgroundTaskRepository(session_factory=async_session_factory)

    expected = [f"step-{i}" for i in range(5)]

    async def producer() -> None:
        await asyncio.sleep(0.3)  # let endpoint start LISTEN
        # Fire all five as fast as possible (back-to-back awaits, no sleeps).
        for i, msg in enumerate(expected):
            await emitter.update(percent=(i + 1) / 5.0, message=msg, data=None)
        await repo.mark_result_ready(task_id=task_id, result={"ok": True})
        await repo.mark_complete(task_id=task_id)

    producer_task = asyncio.create_task(producer())
    resp = await authed_client.get(
        f"/api/v1/chats/{chat_id}/tasks/{task_id}/events"
    )
    await producer_task

    assert resp.status_code == 200
    progress_chunks = _parse_progress(resp.text)
    messages = [c["data"]["message"] for c in progress_chunks]
    assert messages == expected, (
        f"expected {expected} in order, got {messages}"
    )
    # No duplicates: set length equals list length.
    assert len(set(messages)) == len(messages), (
        f"duplicates detected: {messages}"
    )


@pytest.mark.asyncio
async def test_replay_preserves_order_for_presized_batch(
    authed_client: httpx.AsyncClient,
    authed_user_id: UUID,
    app_notify_dispatcher: Any,
) -> None:
    del app_notify_dispatcher
    """Five rows persisted BEFORE connect replay in id order."""
    chat_id = uuid4()
    task_id = uuid4()
    await _seed_chat_and_task(
        user_id=authed_user_id, chat_id=chat_id, task_id=task_id
    )

    emitter = TaskProgressEmitter(
        task_id=task_id, chat_id=chat_id, session_factory=async_session_factory
    )
    repo = BackgroundTaskRepository(session_factory=async_session_factory)

    expected = [f"pre-{i}" for i in range(5)]
    for i, msg in enumerate(expected):
        await emitter.update(percent=(i + 1) / 5.0, message=msg, data=None)
    await repo.mark_result_ready(task_id=task_id, result={"ok": True})
    await repo.mark_complete(task_id=task_id)

    resp = await authed_client.get(
        f"/api/v1/chats/{chat_id}/tasks/{task_id}/events"
    )
    assert resp.status_code == 200

    progress_chunks = _parse_progress(resp.text)
    messages = [c["data"]["message"] for c in progress_chunks]
    assert messages == expected, (
        f"replay order mismatch: got {messages}"
    )
    assert len(set(messages)) == len(messages), (
        f"replay duplicates: {messages}"
    )


@pytest.mark.asyncio
async def test_mixed_replay_then_live_no_duplicate_rows(
    authed_client: httpx.AsyncClient,
    authed_user_id: UUID,
    app_notify_dispatcher: Any,
) -> None:
    del app_notify_dispatcher
    """Some rows exist before connect, more arrive after — no id is seen twice."""
    chat_id = uuid4()
    task_id = uuid4()
    await _seed_chat_and_task(
        user_id=authed_user_id, chat_id=chat_id, task_id=task_id
    )

    emitter = TaskProgressEmitter(
        task_id=task_id, chat_id=chat_id, session_factory=async_session_factory
    )
    repo = BackgroundTaskRepository(session_factory=async_session_factory)

    pre_msgs = [f"pre-{i}" for i in range(3)]
    live_msgs = [f"live-{i}" for i in range(3)]

    for i, msg in enumerate(pre_msgs):
        await emitter.update(percent=(i + 1) / 10.0, message=msg, data=None)

    async def producer() -> None:
        await asyncio.sleep(0.3)
        for i, msg in enumerate(live_msgs):
            await emitter.update(
                percent=0.5 + (i + 1) / 10.0, message=msg, data=None
            )
        await repo.mark_result_ready(task_id=task_id, result={"ok": True})
        await repo.mark_complete(task_id=task_id)

    producer_task = asyncio.create_task(producer())
    resp = await authed_client.get(
        f"/api/v1/chats/{chat_id}/tasks/{task_id}/events"
    )
    await producer_task

    assert resp.status_code == 200
    progress_chunks = _parse_progress(resp.text)
    messages = [c["data"]["message"] for c in progress_chunks]
    # Order: all pre_msgs (in order), then all live_msgs (in order).
    assert messages == pre_msgs + live_msgs, (
        f"mixed order mismatch: got {messages}"
    )
    assert len(set(messages)) == len(messages), (
        f"mixed duplicates: {messages}"
    )
