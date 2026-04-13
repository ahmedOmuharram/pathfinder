"""Unit tests for ``services.chat._state_mapping.events_for_decision``.

Verifies the translation table from semantic ``PhaseDecision.next_action``
literals to the legacy state-machine event names (``finish_scoping``,
``submit_draft``/``approve``, ...) the pipeline expects.
"""

from __future__ import annotations

import pytest

from pathfinder.ai.agents._phase_decisions import (
    DiscoveryDecision,
    ExecutionDecision,
    PlanningDecision,
    ScopingDecision,
    VerificationDecision,
)
from pathfinder.ai.orchestration.pipeline import create_pipeline
from pathfinder.services.chat._state_mapping import events_for_decision


def _scoping(action: str) -> ScopingDecision:
    return ScopingDecision(
        next_action=action,  # type: ignore[arg-type]
        problem_frame="frame",
        discovered_searches=[],
        reason="reason",
    )


def _discovery(action: str) -> DiscoveryDecision:
    return DiscoveryDecision(
        next_action=action,  # type: ignore[arg-type]
        discovered_searches=[],
        reason="reason",
    )


def _planning(action: str) -> PlanningDecision:
    return PlanningDecision(
        next_action=action,  # type: ignore[arg-type]
        plan_id="p_x",
        reason="reason",
    )


def _execution(action: str) -> ExecutionDecision:
    return ExecutionDecision(
        next_action=action,  # type: ignore[arg-type]
        executed_steps=[],
        reason="reason",
    )


def _verification(action: str) -> VerificationDecision:
    return VerificationDecision(
        next_action=action,  # type: ignore[arg-type]
        verification_notes="n",
        reason="reason",
    )


def test_scoping_advance_to_discovery_fires_finish_scoping() -> None:
    assert events_for_decision(_scoping("advance_to_discovery")) == (
        "finish_scoping",
    )


def test_scoping_advance_to_planning_falls_through_via_discovery() -> None:
    # No direct scoping→planning edge exists; we still emit finish_scoping and
    # let discovery short-circuit if it wants to.
    assert events_for_decision(_scoping("advance_to_planning")) == (
        "finish_scoping",
    )


def test_scoping_need_more_input_returns_empty_tuple() -> None:
    assert events_for_decision(_scoping("need_more_input")) == ()


def test_discovery_advance_to_planning_fires_finish_discovery() -> None:
    assert events_for_decision(_discovery("advance_to_planning")) == (
        "finish_discovery",
    )


def test_discovery_advance_to_execution_falls_through_via_planning() -> None:
    assert events_for_decision(_discovery("advance_to_execution")) == (
        "finish_discovery",
    )


def test_discovery_need_more_input_returns_empty_tuple() -> None:
    assert events_for_decision(_discovery("need_more_input")) == ()


def test_planning_advance_to_execution_emits_submit_plus_approve() -> None:
    # Planning requires two events to reach execution:
    #   submit_draft → awaiting_approval, approve → plan_approved
    # (plan_approved is final; done.state.planning auto-fires transition.)
    assert events_for_decision(_planning("advance_to_execution")) == (
        "submit_draft",
        "approve",
    )


def test_planning_request_revision_stays_inside_planning() -> None:
    assert events_for_decision(_planning("request_revision")) == (
        "submit_draft",
        "request_revision",
    )


def test_planning_abort_fires_abort_planning() -> None:
    assert events_for_decision(_planning("abort")) == ("abort_planning",)


def test_execution_advance_to_verification_fires_finish_execution() -> None:
    assert events_for_decision(_execution("advance_to_verification")) == (
        "finish_execution",
    )


def test_execution_retry_stays_inside_execution() -> None:
    assert events_for_decision(_execution("retry")) == ("retry",)


def test_execution_abort_fires_abort_execution() -> None:
    assert events_for_decision(_execution("abort")) == ("abort_execution",)


def test_verification_complete_fires_finish_verification() -> None:
    assert events_for_decision(_verification("complete")) == (
        "finish_verification",
    )


def test_verification_retry_execution_degrades_to_completion() -> None:
    # No backwards verification→execution edge exists.
    assert events_for_decision(_verification("retry_execution")) == (
        "finish_verification",
    )


def test_verification_abort_fires_abort_verification() -> None:
    assert events_for_decision(_verification("abort")) == (
        "abort_verification",
    )


# ---------------------------------------------------------------------------
# End-to-end: the event names must actually drive the real state machine.
# ---------------------------------------------------------------------------


def test_happy_path_drives_state_machine_to_completed() -> None:
    """Scoping→discovery→planning→execution→verification→completed."""
    pipeline = create_pipeline()
    assert pipeline.current_phase == "scoping"

    decisions = [
        _scoping("advance_to_discovery"),
        _discovery("advance_to_planning"),
        _planning("advance_to_execution"),
        _execution("advance_to_verification"),
        _verification("complete"),
    ]
    expected_phases = ["discovery", "planning", "execution", "verification", "completed"]

    for decision, expected in zip(decisions, expected_phases, strict=True):
        for event in events_for_decision(decision):
            pipeline.send(event)
        assert pipeline.current_phase == expected, (
            f"after {decision!r} events, expected {expected}, got {pipeline.current_phase}"
        )

    assert pipeline.is_done


@pytest.mark.parametrize(
    ("action", "expected_events"),
    [
        ("abort", ("abort_planning",)),
    ],
)
def test_planning_abort_reaches_failed_state(
    action: str, expected_events: tuple[str, ...]
) -> None:
    pipeline = create_pipeline()
    # Drive to planning first.
    pipeline.send("finish_scoping")
    pipeline.send("finish_discovery")
    assert pipeline.current_phase == "planning"

    # Then abort.
    assert events_for_decision(_planning(action)) == expected_events
    for event in expected_events:
        pipeline.send(event)
    assert pipeline.current_phase == "failed"
