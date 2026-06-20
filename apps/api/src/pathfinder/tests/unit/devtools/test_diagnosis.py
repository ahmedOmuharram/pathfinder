from __future__ import annotations

from pathfinder.devtools.diagnosis import diagnose
from pathfinder.devtools.models import (
    CapturedToolCall,
    DecodedError,
    RunSummary,
)


def _failed(seq: int, tool: str, errors: list[DecodedError]) -> CapturedToolCall:
    return CapturedToolCall(
        seq=seq,
        phase="planning",
        tool=tool,
        tool_call_id=f"c{seq}",
        status="failed",
        errors=errors,
        result="boom",
    )


def _call(
    seq: int,
    tool: str,
    status: str,
    *,
    args: dict | None = None,
    result: str | None = None,
    phase: str = "discovery",
) -> CapturedToolCall:
    return CapturedToolCall(
        seq=seq,
        phase=phase,
        tool=tool,
        tool_call_id=f"c{seq}",
        status=status,
        args=args,
        result=result,
    )


def test_detects_validation_catch22_on_same_param() -> None:
    calls = [
        _failed(
            1,
            "create_plan",
            [
                DecodedError(
                    kind="missing_required",
                    search_name="GenesByText",
                    param="document_type",
                ),
            ],
        ),
        _failed(
            2,
            "create_plan",
            [
                DecodedError(
                    kind="unknown_param",
                    search_name="GenesByText",
                    param="document_type",
                ),
            ],
        ),
    ]
    anomalies = diagnose(calls, {}, RunSummary())
    catch22 = [a for a in anomalies if a.kind == "validation_catch_22"]
    assert len(catch22) == 1
    assert "document_type" in catch22[0].message
    assert catch22[0].severity == "critical"
    assert any("create_plan" in e for e in catch22[0].evidence)


def test_detects_loop_on_repeated_tool_failures() -> None:
    calls = [_failed(i, "create_plan", []) for i in range(1, 7)]
    anomalies = diagnose(calls, {}, RunSummary())
    loops = [a for a in anomalies if a.kind == "loop"]
    assert loops
    assert "create_plan" in loops[0].message


def test_detects_silent_zero_from_ledger() -> None:
    ledgers = {"execution": {"build": {"zeroResultSteps": ["s1", "s3"]}}}
    anomalies = diagnose([], ledgers, RunSummary())
    zeros = [a for a in anomalies if a.kind == "silent_zero"]
    assert zeros
    assert "s1" in zeros[0].message or "s1" in str(zeros[0].details)


def test_detects_no_plan_terminal() -> None:
    summary = RunSummary(
        status="error", terminal_error="Planning sub-agent returned no plan."
    )
    anomalies = diagnose([], {}, summary)
    assert any(a.kind == "no_plan" for a in anomalies)


_SERVICE_ERR = (
    "Transient error in get_search_overview: VEuPathDB service error: Request "
    "failed after retries: Server error '500 Internal Server Error' for url "
    "'https://vectorbase.org/.../GenesByRNASeqFoo?expandParams=true'. The service "
    "may be temporarily unavailable. Retrying."
)


def test_detects_repeated_wdk_service_error_on_same_search() -> None:
    calls = [
        _call(
            i,
            "get_search_overview",
            "failed",
            args={"search_name": "GenesByRNASeqFoo"},
            result=_SERVICE_ERR,
        )
        for i in range(1, 4)
    ]
    anomalies = diagnose(calls, {}, RunSummary())
    svc = [a for a in anomalies if a.kind == "wdk_service_error"]
    assert len(svc) == 1
    assert "GenesByRNASeqFoo" in svc[0].message
    assert svc[0].details["count"] == 3
    assert all("get_search_overview" in e for e in svc[0].evidence)


def test_single_service_error_below_threshold_not_flagged() -> None:
    calls = [
        _call(
            1,
            "get_search_overview",
            "failed",
            args={"search_name": "GenesByRNASeqFoo"},
            result=_SERVICE_ERR,
        )
    ]
    anomalies = diagnose(calls, {}, RunSummary())
    assert not [a for a in anomalies if a.kind == "wdk_service_error"]


def test_detects_outage_driven_rejection() -> None:
    call = _call(
        1,
        "update_search_decision",
        "completed",
        args={
            "search_name": "GenesByRNASeqFoo",
            "selection_status": "rejected",
            "rationale": "Dataset is currently unavailable due to server errors and "
            "cannot be inspected for parameter vocabulary.",
            "selection_reason": "Rejected due to service unavailability.",
        },
    )
    anomalies = diagnose([call], {}, RunSummary())
    rej = [a for a in anomalies if a.kind == "outage_driven_rejection"]
    assert len(rej) == 1
    assert "GenesByRNASeqFoo" in rej[0].message


def test_scientific_rejection_not_flagged() -> None:
    call = _call(
        1,
        "update_search_decision",
        "completed",
        args={
            "search_name": "GenesByText",
            "selection_status": "rejected",
            "rationale": "Not the most specific search for the female-adult question.",
            "selection_reason": "A better expression dataset exists.",
        },
    )
    anomalies = diagnose([call], {}, RunSummary())
    assert not [a for a in anomalies if a.kind == "outage_driven_rejection"]


def test_clean_run_has_no_anomalies() -> None:
    calls = [
        CapturedToolCall(
            seq=1, phase="planning", tool="create_plan", status="completed"
        ),
    ]
    summary = RunSummary(status="ok", tokens=20000)
    assert diagnose(calls, {}, summary) == []
