from datetime import UTC, datetime
from typing import cast
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from pathfinder.ai.specialists.context import (
    _control_test_runs,
    _enforce_total_budget,
    _excerpt_from_message,
    _step_summaries,
)
from pathfinder.ai.specialists.types import TurnExcerpt
from pathfinder.persistence.models import BackgroundTask, Conversation


def _conv(
    strategy_ast: object,
    *,
    wdk_strategy_id: int | None = None,
    record_type: str | None = "transcript",
) -> Conversation:
    conv = MagicMock()
    conv.id = uuid4()
    conv.strategy_ast = strategy_ast
    conv.wdk_strategy_id = wdk_strategy_id
    conv.record_type = record_type
    return cast("Conversation", conv)


def _leaf(local_id: str, search_name: str, display_name: str = "") -> dict[str, object]:
    return {
        "id": local_id,
        "searchName": search_name,
        "displayName": display_name or search_name,
        "parameters": {},
    }


def test_step_summaries_walks_recursive_tree_and_resolves_wdk_ids() -> None:
    conv = _conv({
        "name": "kinase strategy",
        "recordType": "transcript",
        "root": {
            "id": "step_root",
            "searchName": "__combine__",
            "displayName": "Kinases ∩ Membrane",
            "operator": "INTERSECT",
            "primaryInput": _leaf("step_a", "GenesByGoTerm", "Kinase genes"),
            "secondaryInput": _leaf("step_b", "GenesByText", "Membrane genes"),
            "parameters": {},
        },
        "wdkStepIds": {"step_a": 101, "step_b": 102, "step_root": 103},
    })
    result = _step_summaries(conv)
    by_local = {s.local_step_id: s for s in result}
    assert set(by_local) == {"step_a", "step_b", "step_root"}
    assert by_local["step_a"].kind == "search"
    assert by_local["step_b"].kind == "search"
    assert by_local["step_root"].kind == "combine"
    assert by_local["step_root"].step_id == 103
    assert by_local["step_a"].step_id == 101
    assert all(s.record_class_name == "transcript" for s in result)


def test_step_summaries_keeps_combine_with_unresolved_wdk_id() -> None:
    conv = _conv({
        "name": "unpushed",
        "recordType": "transcript",
        "root": {
            "id": "step_root",
            "searchName": "__combine__",
            "operator": "UNION",
            "primaryInput": _leaf("step_a", "GenesByText"),
            "secondaryInput": _leaf("step_b", "GenesByText"),
            "parameters": {},
        },
    })
    result = _step_summaries(conv)
    assert len(result) == 3
    combine = next(s for s in result if s.kind == "combine")
    assert combine.step_id is None
    assert combine.search_name == "__combine__"


def test_step_summaries_raises_when_pushed_strategy_missing_wdk_step_ids() -> None:
    conv = _conv(
        {
            "name": "stale",
            "recordType": "transcript",
            "root": _leaf("step_a", "GenesByText"),
        },
        wdk_strategy_id=42,
    )
    with pytest.raises(RuntimeError, match="must be re-pushed"):
        _step_summaries(conv)


def test_step_summaries_handles_empty_or_invalid_ast() -> None:
    assert _step_summaries(_conv(None)) == []
    assert _step_summaries(_conv({})) == []
    assert _step_summaries(_conv({"root": "not-an-object"})) == []


def _bg_task(
    *,
    tool_name: str,
    status: str,
    args: dict[str, object] | None = None,
    result: dict[str, object] | None = None,
) -> BackgroundTask:
    task = MagicMock()
    task.id = uuid4()
    task.tool_name = tool_name
    task.status = status
    task.args = args or {}
    task.result = result
    task.completed_at = None
    return cast("BackgroundTask", task)


def test_control_test_runs_filters_by_tool_name() -> None:
    rows = [
        _bg_task(
            tool_name="run_control_tests_on_step",
            status="complete",
            args={"step_id": 5},
            result={"summary": "ok"},
        ),
        _bg_task(tool_name="optimize_search_parameters", status="running"),
    ]
    runs = _control_test_runs(rows)
    assert len(runs) == 1
    assert runs[0].step_id == 5
    assert runs[0].status == "succeeded"
    assert runs[0].summary == "ok"


def test_control_test_runs_maps_statuses() -> None:
    rows = [
        _bg_task(
            tool_name="run_control_tests_on_step",
            status=raw,
            args={"step_id": 1},
        )
        for raw in ("complete", "failed", "cancelled", "running", "pending")
    ]
    statuses = [r.status for r in _control_test_runs(rows)]
    assert statuses == ["succeeded", "failed", "cancelled", "running", "running"]


def test_excerpt_from_message_drops_tool_payloads_and_counts() -> None:
    msg = MagicMock()
    msg.role = "assistant"
    msg.created_at = datetime.now(UTC)
    msg.parts = [
        {"type": "text", "text": "  Hello there.  "},
        {"type": "reasoning", "text": "thinking..."},
        {"type": "tool-search_memory", "input": {"q": "x"}},
        {"type": "tool-think", "input": {}},
        {"type": "data-graph-snapshot", "data": {}},
    ]
    excerpt = _excerpt_from_message(msg)
    assert excerpt.role == "assistant"
    assert "Hello there." in excerpt.text
    assert "[reasoning] thinking..." in excerpt.text
    assert excerpt.tool_call_count == 2


def test_enforce_total_budget_drops_oldest_first() -> None:
    big = "x" * 2000
    excerpts = [
        TurnExcerpt(role="user", text=big, created_at=datetime.now(UTC)),
        TurnExcerpt(role="assistant", text=big, created_at=datetime.now(UTC)),
        TurnExcerpt(role="user", text=big, created_at=datetime.now(UTC)),
        TurnExcerpt(role="assistant", text=big, created_at=datetime.now(UTC)),
        TurnExcerpt(role="user", text=big, created_at=datetime.now(UTC)),
    ]
    # 10000 chars total > 6000 budget → should drop oldest until under budget
    out = _enforce_total_budget(excerpts, budget=6000)
    assert sum(len(e.text) for e in out) <= 6000
    # The KEPT excerpts should be the most recent ones (tail of input)
    assert len(out) == 3
    assert out == excerpts[-3:]


def test_enforce_total_budget_passthrough_when_under() -> None:
    excerpts = [
        TurnExcerpt(role="user", text="short", created_at=datetime.now(UTC)),
        TurnExcerpt(role="assistant", text="reply", created_at=datetime.now(UTC)),
    ]
    out = _enforce_total_budget(excerpts, budget=6000)
    assert out == excerpts


def test_excerpt_from_message_caps_text_length() -> None:
    msg = MagicMock()
    msg.role = "user"
    msg.created_at = datetime.now(UTC)
    msg.parts = [{"type": "text", "text": "x" * 5000}]
    excerpt = _excerpt_from_message(msg)
    assert len(excerpt.text) == 2000
