from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from uuid import uuid4

from pathfinder.devtools.capture import RunCapture, capture_tracebacks, reset_run_dir


def _write(cap: RunCapture, chunk: dict) -> None:
    asyncio.run(cap.write(chunk))


def _call(phase: str, sub_agent: str, tcid: str, state: str) -> dict:
    return {
        "type": "data-sub-agent-call",
        "data": {
            "phase": phase,
            "subAgent": sub_agent,
            "state": state,
            "toolCallId": tcid,
        },
    }


def _step(
    tool: str, tcid: str, parent: str, state: str, *, args=None, result=None
) -> dict:
    return {
        "type": "data-sub-agent-step",
        "data": {
            "toolName": tool,
            "toolCallId": tcid,
            "parentToolCallId": parent,
            "state": state,
            "args": args,
            "resultSummary": result,
        },
    }


def _new(tmp_path: Path) -> RunCapture:
    return RunCapture(
        conversation_id=uuid4(), turn_id=uuid4(), run_dir=tmp_path, quiet=True
    )


def test_tool_call_pairs_start_and_complete(tmp_path: Path) -> None:
    cap = _new(tmp_path)
    _write(cap, _step("think", "c1", "p1", "started", args={"thought": "x"}))
    _write(cap, _step("think", "c1", "p1", "completed", result="done"))
    calls = cap.tool_calls()
    assert len(calls) == 1
    assert calls[0].tool == "think"
    assert calls[0].status == "completed"
    assert calls[0].args == {"thought": "x"}
    assert calls[0].result == "done"


def test_failed_tool_call_decodes_errors(tmp_path: Path) -> None:
    cap = _new(tmp_path)
    _write(cap, _step("create_plan", "c2", "p1", "started", args={"steps": []}))
    _write(
        cap,
        _step(
            "create_plan",
            "c2",
            "p1",
            "failed",
            result='{"ok": false, "code": "VALIDATION_ERROR", '
            '"message": "Missing required parameters: document_type", '
            '"details": {"errors": [{"context": {"searchName": "GenesByText", '
            '"missing": ["document_type"]}}]}}',
        ),
    )
    call = cap.tool_calls()[0]
    assert call.status == "failed"
    assert any(
        e.param == "document_type" and e.kind == "missing_required" for e in call.errors
    )


def test_tokens_read_total_tokens_from_turn_usage(tmp_path: Path) -> None:
    cap = _new(tmp_path)
    _write(
        cap,
        {"type": "data-turn-usage", "data": {"totalTokens": 540898, "costUsd": "0.19"}},
    )
    s = cap.summary()
    assert s.tokens == 540898
    assert abs(s.cost_usd - 0.19) < 1e-9


def test_approval_tool_name_comes_from_tool_input(tmp_path: Path) -> None:
    cap = _new(tmp_path)
    _write(
        cap,
        {"type": "tool-input-available", "toolCallId": "ca", "toolName": "submit_plan"},
    )
    _write(
        cap, {"type": "tool-approval-request", "approvalId": "ca", "toolCallId": "ca"}
    )
    assert cap.pending_approval == ("submit_plan", "ca")


def test_flush_writes_full_fidelity_artifacts(tmp_path: Path) -> None:
    cap = _new(tmp_path)
    big_args = {
        "steps": [{"parameters": {"text_expression": "odorant binding protein"}}]
    }
    _write(cap, _call("planning", "build_plan", "p1", "started"))
    _write(cap, _step("create_plan", "c1", "p1", "started", args=big_args))
    _write(cap, _step("create_plan", "c1", "p1", "completed", result="x" * 5000))
    out = cap.flush()
    assert (out / "events.jsonl").exists()
    assert (out / "summary.json").exists()
    tool_files = sorted((out / "tools").glob("*.json"))
    assert len(tool_files) == 1
    payload = json.loads(tool_files[0].read_text())
    assert payload["args"] == big_args
    assert len(payload["result"]) == 5000  # not truncated on disk


def test_reset_run_dir_removes_stale_artifacts_keeps_unrelated(tmp_path: Path) -> None:
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "99-stale.json").write_text("{}")
    (tmp_path / "wdk").mkdir()
    (tmp_path / "wdk" / "01-old.json").write_text("{}")
    (tmp_path / "events.jsonl").write_text("old\n")
    (tmp_path / "diagnosis.json").write_text("[]")
    (tmp_path / "notes.txt").write_text("keep me")
    reset_run_dir(tmp_path)
    assert not (tmp_path / "tools" / "99-stale.json").exists()
    assert not (tmp_path / "wdk").exists()
    assert not (tmp_path / "events.jsonl").exists()
    assert not (tmp_path / "diagnosis.json").exists()
    assert (tmp_path / "notes.txt").read_text() == "keep me"
    assert tmp_path.is_dir()


def test_reset_run_dir_creates_missing_dir(tmp_path: Path) -> None:
    target = tmp_path / "fresh"
    reset_run_dir(target)
    assert target.is_dir()


def test_flush_after_reset_has_no_stale_tool_files(tmp_path: Path) -> None:
    stale = _new(tmp_path)
    _write(stale, _step("create_plan", "old1", "p1", "started"))
    _write(stale, _step("create_plan", "old1", "p1", "failed", result="boom"))
    stale.flush()
    assert (tmp_path / "tools" / "01-create_plan.json").exists()

    reset_run_dir(tmp_path)
    fresh = _new(tmp_path)
    _write(fresh, _step("think", "new1", "p1", "started"))
    _write(fresh, _step("think", "new1", "p1", "completed", result="ok"))
    fresh.flush()
    tool_files = sorted((tmp_path / "tools").glob("*.json"))
    assert [p.name for p in tool_files] == ["01-think.json"]


def test_events_jsonl_has_one_line_per_chunk(tmp_path: Path) -> None:
    cap = _new(tmp_path)
    _write(cap, {"type": "start", "messageId": "m"})
    _write(cap, {"type": "finish"})
    out = cap.flush()
    lines = (out / "events.jsonl").read_text().splitlines()
    assert len(lines) == 2


def test_capture_tracebacks_writes_exc_info(tmp_path: Path) -> None:
    logger = logging.getLogger("pathfinder.test.capture")
    msg = "synthetic boom"

    def _boom() -> None:
        raise ValueError(msg)

    with capture_tracebacks(tmp_path):
        try:
            _boom()
        except ValueError:
            logger.exception("tool blew up")
    files = sorted((tmp_path / "errors").glob("*.txt"))
    assert len(files) == 1
    body = files[0].read_text()
    assert "ValueError: synthetic boom" in body
    assert "Traceback" in body


def test_capture_tracebacks_ignores_non_exception_logs(tmp_path: Path) -> None:
    logger = logging.getLogger("pathfinder.test.capture2")
    with capture_tracebacks(tmp_path):
        logger.info("just info, no exception")
    assert not (tmp_path / "errors").exists() or not list(
        (tmp_path / "errors").glob("*.txt")
    )


def test_capture_tracebacks_captures_structlog_field_traceback(tmp_path: Path) -> None:
    logger = logging.getLogger("pathfinder.test.capture3")
    with capture_tracebacks(tmp_path):
        logger.error(
            "Unknown tool error", extra={"traceback": "Traceback: AppNotOpen boom"}
        )
    files = sorted((tmp_path / "errors").glob("*.txt"))
    assert len(files) == 1
    assert "AppNotOpen boom" in files[0].read_text()
