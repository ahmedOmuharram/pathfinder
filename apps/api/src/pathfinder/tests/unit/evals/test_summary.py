"""The run summary: the numbers a trend is drawn from."""

from __future__ import annotations

from pathfinder.evals.scoring import CaseDifference
from pathfinder.evals.summary import CaseResult, EvalRunSummary


def _summary(*cases: CaseResult) -> EvalRunSummary:
    return EvalRunSummary(
        harness="pydantic-evals",
        provider="mock",
        assistant_id="pathfinder",
        ran_at="2026-08-23T00:00:00+00:00",
        cases=list(cases),
    )


def test_an_empty_run_reports_a_zero_pass_rate() -> None:
    summary = _summary()

    assert summary.case_count == 0
    assert summary.pass_rate == 0.0


def test_a_green_run_reports_one() -> None:
    summary = _summary(
        CaseResult(name="a", passed=True),
        CaseResult(name="b", passed=True),
    )

    assert summary.passed == 2
    assert summary.failed == 0
    assert summary.pass_rate == 1.0


def test_an_errored_case_counts_as_neither_passed_nor_failed() -> None:
    summary = _summary(
        CaseResult(name="a", passed=True),
        CaseResult(name="b", passed=False, error="boom"),
    )

    assert summary.passed == 1
    assert summary.failed == 0
    assert summary.errored == 1
    assert summary.case_count == 2
    assert summary.pass_rate == 0.5


def test_the_serialized_summary_carries_the_counts_and_the_differences() -> None:
    summary = _summary(
        CaseResult(
            name="a",
            passed=False,
            differences=[
                CaseDifference(field="structure", expected="x", actual="y"),
            ],
        ),
    )

    payload = summary.model_dump(by_alias=True, mode="json")

    assert payload["passRate"] == 0.0
    assert payload["caseCount"] == 1
    assert payload["cases"][0]["differences"][0]["field"] == "structure"
