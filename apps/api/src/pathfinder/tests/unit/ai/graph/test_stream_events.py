from __future__ import annotations

from uuid import uuid4

from shared_py.stream_events import CustomEvent

from pathfinder.ai.graph.stream_events import (
    background_task_started_event,
    phase_change_event,
    phase_finish_event,
    phase_start_event,
)


def test_phase_change_event() -> None:
    ev = phase_change_event(phase="scoping", status="started", reason="initial turn")
    assert isinstance(ev, CustomEvent)
    assert ev.kind == "data-phase-change"
    assert ev.data["phase"] == "scoping"
    assert ev.data["status"] == "started"
    assert ev.data["reason"] == "initial turn"


def test_background_task_started_event() -> None:
    task_id = uuid4()
    ev = background_task_started_event(
        task_id=task_id,
        tool_name="optimize_search_parameters",
        estimated_duration_seconds=900,
    )
    assert ev.kind == "data-background-task-started"
    assert ev.data["taskId"] == str(task_id)
    assert ev.data["toolName"] == "optimize_search_parameters"
    assert ev.data["estimatedDurationSeconds"] == 900


def test_phase_start_event_metadata() -> None:
    ev = phase_start_event(phase="discovery", trace_id="t-1", model="opus")
    assert ev.kind == "data-phase-start"
    assert ev.data["phase"] == "discovery"
    assert ev.data["traceId"] == "t-1"
    assert ev.data["model"] == "opus"


def test_phase_finish_event_reason() -> None:
    ev = phase_finish_event(phase="verification", reason="stop")
    assert ev.kind == "data-phase-finish"
    assert ev.data["phase"] == "verification"
    assert ev.data["reason"] == "stop"
