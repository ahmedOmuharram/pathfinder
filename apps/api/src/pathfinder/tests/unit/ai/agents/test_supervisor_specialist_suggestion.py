from __future__ import annotations

import pytest
from pydantic import ValidationError

from pathfinder.ai.agents.supervisor import SupervisorDecision


def test_decision_serializes_suggested_specialist_validate() -> None:
    d = SupervisorDecision(
        to="execution",
        reason="user is asking whether the strategy is right",
        suggested_specialist="validate",
    )
    dumped = d.model_dump(mode="json")
    assert dumped["suggested_specialist"] == "validate"
    assert dumped["to"] == "execution"


def test_decision_serializes_suggested_specialist_research() -> None:
    d = SupervisorDecision(
        to="question",
        reason="open biological question",
        answer="Plasmodium falciparum has 14 chromosomes.",
        suggested_specialist="research",
    )
    dumped = d.model_dump(mode="json")
    assert dumped["suggested_specialist"] == "research"


def test_decision_default_no_suggestion_omitted_with_exclude_none() -> None:
    d = SupervisorDecision(to="planning", reason="proceed to planning")
    dumped = d.model_dump(exclude_none=True)
    assert "suggested_specialist" not in dumped
    assert d.suggested_specialist is None


def test_decision_rejects_invalid_specialist_kind() -> None:
    with pytest.raises(ValidationError):
        SupervisorDecision.model_validate(
            {
                "to": "scoping",
                "reason": "x",
                "suggested_specialist": "optimize",
            },
        )


def test_decision_accepts_validate_kind_via_model_validate() -> None:
    d = SupervisorDecision.model_validate(
        {
            "to": "scoping",
            "reason": "x",
            "suggested_specialist": "validate",
        },
    )
    assert d.suggested_specialist == "validate"


def test_decision_accepts_research_kind_via_model_validate() -> None:
    d = SupervisorDecision.model_validate(
        {
            "to": "scoping",
            "reason": "x",
            "suggested_specialist": "research",
        },
    )
    assert d.suggested_specialist == "research"
