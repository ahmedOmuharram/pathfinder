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
    dec = ScopingDecision(next_action="advance_to_discovery")
    assert dec.next_action == "advance_to_discovery"


def test_scoping_decision_rejects_unknown_next_action() -> None:
    with pytest.raises(ValidationError):
        ScopingDecision.model_validate({"next_action": "teleport_to_execution"})


def test_discovery_decision_happy_path() -> None:
    dec = DiscoveryDecision(next_action="advance_to_planning")
    assert dec.next_action == "advance_to_planning"


def test_planning_decision_happy_path() -> None:
    dec = PlanningDecision(next_action="advance_to_execution")
    assert dec.next_action == "advance_to_execution"


def test_execution_decision_happy_path() -> None:
    dec = ExecutionDecision(next_action="advance_to_verification")
    assert dec.next_action == "advance_to_verification"


def test_verification_decision_happy_path() -> None:
    dec = VerificationDecision(next_action="complete")
    assert dec.next_action == "complete"
