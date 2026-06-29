from __future__ import annotations

from typing import get_args
from uuid import uuid4

import pytest
from pydantic import ValidationError

from pathfinder.ai.agents.state import SearchOverview
from pathfinder.ai.graph.state import (
    PHASE_NAMES,
    PhaseDisposition,
    PhaseName,
    PipelineState,
    VerificationDigest,
)
from pathfinder.domain.strategy.operational_spec import Criterion, OperationalSpec


@pytest.fixture
def base_state() -> PipelineState:
    return PipelineState(
        conversation_id=uuid4(),
        user_id=uuid4(),
        site_id="plasmodb",
        mode="strategy",
    )


def test_phase_names_constant_matches_literal_args() -> None:
    assert set(PHASE_NAMES) == set(get_args(PhaseName))
    assert PHASE_NAMES == (
        "frame",
        "build",
        "verification",
    )


def test_state_minimum_construction(base_state: PipelineState) -> None:
    assert base_state.site_id == "plasmodb"
    assert base_state.mode == "strategy"
    assert base_state.user_prompt == ""
    assert base_state.user_parts == []
    assert base_state.discovered_searches == {}
    assert base_state.operational_spec is None
    assert base_state.verification_digest is None
    assert base_state.last_build_outcome is None
    assert base_state.user_intent is None
    # Cross-phase / cross-turn context now flows through typed fields, not
    # a raw model trace — drop the field so checkpoints stay small.
    assert not hasattr(base_state, "message_history")
    assert not hasattr(base_state, "current_phase")
    assert not hasattr(base_state, "supervisor_log")
    assert not hasattr(base_state, "specialist_mode")


def test_state_carries_verification_digest(
    base_state: PipelineState,
) -> None:
    """Verification digest is the only typed exit signal under the Lead
    architecture; round-trip through JSON proves it survives the
    LangGraph checkpoint shape."""
    digest = VerificationDigest(
        disposition=PhaseDisposition.DONE,
        prose="Strategy ready.",
        reason="verification successful",
        success=True,
        key_findings=["1234 hits"],
    )
    state = base_state.model_copy(update={"verification_digest": digest})
    rehydrated = PipelineState.model_validate(state.model_dump(mode="json"))
    assert rehydrated.verification_digest is not None
    assert rehydrated.verification_digest.disposition == PhaseDisposition.DONE
    assert rehydrated.verification_digest.success is True
    assert rehydrated.verification_digest.key_findings == ["1234 hits"]


def test_state_carries_operational_spec(base_state: PipelineState) -> None:
    spec = OperationalSpec(
        goal="find drug targets",
        interpreted_goal="find drug targets in P. falciparum",
        organism_scope="P. falciparum",
        criteria=[
            Criterion(id="c1", text="kinases", search_name="GenesByGoTerm"),
        ],
    )
    state = base_state.model_copy(update={"operational_spec": spec})
    rehydrated = PipelineState.model_validate(state.model_dump(mode="json"))
    assert rehydrated.operational_spec is not None
    assert rehydrated.operational_spec.goal == "find drug targets"
    assert rehydrated.operational_spec.criteria[0].search_name == "GenesByGoTerm"


def test_state_carries_discovered_searches(base_state: PipelineState) -> None:
    overview = SearchOverview(
        search_name="GenesByExpression",
        display_name="Genes by Expression",
        record_type="transcript",
        description="",
        parameter_names=["dataset"],
        required_params=["dataset"],
    )
    state = base_state.model_copy(
        update={"discovered_searches": {"GenesByExpression": overview}}
    )
    rehydrated = PipelineState.model_validate(state.model_dump(mode="json"))
    assert "GenesByExpression" in rehydrated.discovered_searches
    assert (
        rehydrated.discovered_searches["GenesByExpression"].display_name
        == "Genes by Expression"
    )


def test_state_rejects_negative_total_tokens() -> None:
    """Sanity: PipelineState validation works on at least one field."""
    state = PipelineState(
        conversation_id=uuid4(),
        user_id=uuid4(),
        site_id="plasmodb",
        mode="strategy",
        turn_total_tokens=42,
    )
    assert state.turn_total_tokens == 42
    with pytest.raises(ValidationError):
        PipelineState.model_validate(
            {
                "conversation_id": str(uuid4()),
                "user_id": str(uuid4()),
                "site_id": "plasmodb",
                "mode": "strategy",
                "turn_total_tokens": "not a number",
            },
        )
