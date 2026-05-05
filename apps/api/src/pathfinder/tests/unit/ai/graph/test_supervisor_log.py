from __future__ import annotations

from typing import Any

from pathfinder.ai.graph.state import SupervisorEvent
from pathfinder.ai.graph.supervisor_log import (
    format_supervisor_log,
    record_supervisor_event,
)


def test_record_appends_to_log() -> None:
    log: list[SupervisorEvent] = []
    event = SupervisorEvent(
        kind="supervisor_note", summary="hello", phase="planning",
    )
    record_supervisor_event(log, None, event)
    assert log == [event]


def test_record_emits_envelope_chunk_to_writer() -> None:
    captured: list[dict[str, Any]] = []

    def writer(payload: dict[str, Any]) -> None:
        captured.append(payload)

    log: list[SupervisorEvent] = []
    record_supervisor_event(
        log,
        writer,
        SupervisorEvent(
            kind="phase_enter", summary="entered planning", phase="planning",
        ),
    )
    assert len(captured) == 1
    assert "chunk" in captured[0]
    chunk = captured[0]["chunk"]
    assert chunk["type"] == "data-supervisor-context"
    assert chunk["data"]["kind"] == "phase_enter"
    assert chunk["data"]["summary"] == "entered planning"
    assert chunk["data"]["phase"] == "planning"


def test_record_no_writer_does_not_raise() -> None:
    log: list[SupervisorEvent] = []
    record_supervisor_event(
        log, None,
        SupervisorEvent(kind="route", summary="supervisor → end"),
    )
    assert len(log) == 1


def test_format_empty_log_returns_empty_string() -> None:
    assert format_supervisor_log([]) == ""


def test_format_log_renders_timeline_with_kind_and_phase() -> None:
    events = [
        SupervisorEvent(
            kind="phase_enter", summary="entered scoping", phase="scoping",
        ),
        SupervisorEvent(
            kind="phase_exit",
            summary="scoping done",
            phase="scoping",
            detail="ready_for_wdk",
        ),
        SupervisorEvent(kind="route", summary="supervisor → discovery"),
    ]
    rendered = format_supervisor_log(events)
    assert "Orchestrator running context" in rendered
    assert "[phase_enter/scoping]" in rendered
    assert "[phase_exit/scoping]" in rendered
    assert "[route]" in rendered
    assert "ready_for_wdk" in rendered
