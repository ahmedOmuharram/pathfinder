"""The thread log keeps the newest not-due update, per lane."""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

import pytest
from assistant_core.platform.db import AsyncSession

from pathfinder.jobs import progress
from pathfinder.jobs.progress import (
    TaskProgressEmitter,
    _PendingProgress,
    _ThreadLog,
)


def _row(percent: float) -> _PendingProgress:
    return _PendingProgress(percent=percent, message="working", data=None)


async def test_a_concurrent_offer_survives_a_slow_append(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release = asyncio.Event()
    release.set()
    written: list[dict[str, Any]] = []

    async def fake_append(*, conversation_id: object, chunk: dict[str, Any]) -> int:
        del conversation_id
        await release.wait()
        written.append(chunk)
        return len(written)

    monkeypatch.setattr(progress, "append_chunk", fake_append)
    log = _ThreadLog(conversation_id=uuid4(), task_id=uuid4())

    await log.offer(_row(0.10))
    release.clear()
    due = asyncio.ensure_future(log.offer(_row(0.15)))
    await asyncio.sleep(0)
    await log.offer(_row(0.12))
    release.set()
    await due
    await log.write_last()

    assert [chunk["data"]["percent"] for chunk in written] == [0.10, 0.15, 0.12]


def _no_session() -> AsyncSession:
    msg = "this test writes nothing to the database"
    raise AssertionError(msg)


async def test_a_lane_suffixes_the_id_of_every_chunk_it_writes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    written: list[dict[str, Any]] = []

    async def fake_append(*, conversation_id: object, chunk: dict[str, Any]) -> int:
        del conversation_id
        written.append(chunk)
        return len(written)

    monkeypatch.setattr(progress, "append_chunk", fake_append)
    task_id = uuid4()
    log = _ThreadLog(conversation_id=uuid4(), task_id=task_id, lane="v3")

    await log.offer(_row(0.10))

    assert [chunk["id"] for chunk in written] == [f"{task_id}:v3"]
    assert written[0]["data"]["taskId"] == str(task_id)


async def test_every_lane_keeps_a_budget_and_an_id_of_its_own(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    written: list[dict[str, Any]] = []

    async def fake_append(*, conversation_id: object, chunk: dict[str, Any]) -> int:
        del conversation_id
        written.append(chunk)
        return len(written)

    monkeypatch.setattr(progress, "append_chunk", fake_append)
    task_id = uuid4()
    parent = TaskProgressEmitter(
        task_id=task_id,
        conversation_id=uuid4(),
        session_factory=_no_session,
    )

    for variant in ("v0", "v1", "v2", "v3", "v4"):
        child = parent.scoped(variantId=variant)
        await child._thread_log.offer(_row(0.0))

    assert [chunk["id"] for chunk in written] == [f"{task_id}:v{n}" for n in range(5)]


async def test_a_child_that_scopes_nothing_keeps_the_bare_task_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    written: list[dict[str, Any]] = []

    async def fake_append(*, conversation_id: object, chunk: dict[str, Any]) -> int:
        del conversation_id
        written.append(chunk)
        return len(written)

    monkeypatch.setattr(progress, "append_chunk", fake_append)
    task_id = uuid4()
    parent = TaskProgressEmitter(
        task_id=task_id,
        conversation_id=uuid4(),
        session_factory=_no_session,
    )

    await parent.scoped()._thread_log.offer(_row(0.0))

    assert [chunk["id"] for chunk in written] == [str(task_id)]
