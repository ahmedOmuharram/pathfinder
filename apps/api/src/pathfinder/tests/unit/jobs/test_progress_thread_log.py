"""The thread log keeps the newest not-due update across a slow append."""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

import pytest

from pathfinder.jobs import progress
from pathfinder.jobs.progress import _PendingProgress, _ThreadLog


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
