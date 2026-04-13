"""Tests for typed phase-decision outputs used as agent output_type=."""

import pytest
from pydantic import ValidationError

from pathfinder.ai.agents._phase_decisions import (
    DiscoveryDecision,
    ExecutionDecision,
    PlanningDecision,
    ScopingDecision,
    VerificationDecision,
)


def test_scoping_decision_happy_path() -> None:
    dec = ScopingDecision(
        next_action="advance_to_discovery",
        problem_frame="drug targets for PfATP4",
        discovered_searches=["GenesByOrthologPattern"],
        reason="clear bio intent",
    )
    assert dec.next_action == "advance_to_discovery"
    assert dec.problem_frame == "drug targets for PfATP4"
    assert dec.discovered_searches == ["GenesByOrthologPattern"]
    assert dec.reason == "clear bio intent"


def test_scoping_decision_rejects_unknown_next_action() -> None:
    with pytest.raises(ValidationError):
        ScopingDecision.model_validate(
            {
                "next_action": "teleport_to_execution",
                "problem_frame": "...",
                "reason": "...",
            }
        )


def test_discovery_decision_requires_advance_target() -> None:
    with pytest.raises(ValidationError):
        DiscoveryDecision.model_validate(
            {
                "next_action": "advance_to_planning",
                # missing required fields discovered_searches + reason
            }
        )


def test_planning_decision_happy_path() -> None:
    dec = PlanningDecision(
        next_action="advance_to_execution",
        plan_id="p_x",
        reason="plan approved",
    )
    assert dec.plan_id == "p_x"
    assert dec.next_action == "advance_to_execution"


def test_execution_decision_happy_path() -> None:
    dec = ExecutionDecision(
        next_action="advance_to_verification",
        executed_steps=["step_1", "step_2"],
        reason="all steps applied",
    )
    assert len(dec.executed_steps) == 2
    assert dec.executed_steps == ["step_1", "step_2"]
    assert dec.next_action == "advance_to_verification"


def test_verification_decision_happy_path() -> None:
    dec = VerificationDecision(
        next_action="complete",
        verification_notes="sanity checks pass",
        reason="done",
    )
    assert dec.next_action == "complete"
    assert dec.verification_notes == "sanity checks pass"
    assert dec.reason == "done"
