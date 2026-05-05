from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock

import pytest

from pathfinder.ai.graph.state import SupervisorEvent
from pathfinder.ai.tools.standalone.cognition import journal


@dataclass
class _Deps:
    supervisor_log: list[SupervisorEvent] = field(default_factory=list)
    writer: Any = None


@pytest.mark.asyncio
async def test_journal_appends_and_returns_noted() -> None:
    deps = _Deps()
    ctx = MagicMock()
    ctx.deps = deps
    result = await journal(
        ctx,
        kind="supervisor_note",
        summary="picked discovery over planning",
        detail="frame had unresolved organism scope",
        phase="scoping",
        refs=["frame_v1"],
    )
    assert result == "noted"
    assert len(deps.supervisor_log) == 1
    event = deps.supervisor_log[0]
    assert event.kind == "supervisor_note"
    assert event.summary == "picked discovery over planning"
    assert event.detail == "frame had unresolved organism scope"
    assert event.phase == "scoping"
    assert event.refs == ["frame_v1"]


@pytest.mark.asyncio
async def test_journal_emits_chunk_via_writer() -> None:
    captured: list[dict[str, Any]] = []

    def writer(payload: dict[str, Any]) -> None:
        captured.append(payload)

    deps = _Deps(writer=writer)
    ctx = MagicMock()
    ctx.deps = deps
    await journal(
        ctx, kind="route", summary="supervisor → execution",
    )
    assert len(captured) == 1
    chunk = captured[0]["chunk"]
    assert chunk["type"] == "data-supervisor-context"
    assert chunk["data"]["summary"] == "supervisor → execution"
