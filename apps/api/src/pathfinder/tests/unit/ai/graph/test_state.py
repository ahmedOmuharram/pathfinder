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
    PhaseOutcome,
    PipelineState,
    ProblemFrame,
)


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
        "scoping",
        "discovery",
        "planning",
        "execution",
        "verification",
    )


def test_state_minimum_construction(base_state: PipelineState) -> None:
    assert base_state.site_id == "plasmodb"
    assert base_state.mode == "strategy"
    assert base_state.user_prompt == ""
    assert base_state.user_parts == []
    assert base_state.discovered_searches == {}
    assert base_state.problem_frame is None
    assert base_state.current_phase is None
    assert base_state.supervisor_call_count == 0
    assert base_state.phase_call_counts == {}
    assert base_state.last_routing_reason is None
    assert base_state.last_assistant_prose == ""
    assert base_state.last_verification_message_id is None
    # Cross-phase / cross-turn context now flows through typed fields, not
    # a raw model trace — drop the field so checkpoints stay small.
    assert not hasattr(base_state, "message_history")


def test_state_rejects_unknown_phase_name() -> None:
    with pytest.raises(ValidationError):
        PipelineState(
            conversation_id=uuid4(),
            user_id=uuid4(),
            site_id="plasmodb",
            mode="strategy",
            current_phase="bogus",  # type: ignore[arg-type]
        )


def test_state_carries_last_phase_outcome_across_phases(
    base_state: PipelineState,
) -> None:
    """The handoff between phases now flows through ``last_phase_outcome``
    instead of a raw model trace. Round-tripping through JSON proves it
    survives the LangGraph checkpoint shape, which is what enables the
    ``pinned_last_phase_outcome`` instruction to render for the next phase."""
    outcome = PhaseOutcome(
        disposition=PhaseDisposition.HANDOFF,
        prose=(
            "Discovered GenesByGoTerm and GenesByTransmembrane as anchors; "
            "rejected GenesByMicroarray (user wants RNA-seq)."
        ),
        reason="ready to plan",
        handoff_to="planning",
        note_refs=["note_a", "note_b"],
    )
    state = base_state.model_copy(
        update={"last_phase_outcome": outcome, "current_phase": "discovery"},
    )
    rehydrated = PipelineState.model_validate(state.model_dump(mode="json"))
    assert rehydrated.last_phase_outcome is not None
    assert rehydrated.last_phase_outcome.disposition == PhaseDisposition.HANDOFF
    assert rehydrated.last_phase_outcome.handoff_to == "planning"
    assert rehydrated.last_phase_outcome.note_refs == ["note_a", "note_b"]


def test_state_carries_problem_frame(base_state: PipelineState) -> None:
    frame = ProblemFrame(
        user_goal="find drug targets",
        interpreted_goal="find drug targets in P. falciparum",
        organism_scope="P. falciparum",
        ready_for_wdk_discovery=True,
        confidence=0.8,
    )
    state = base_state.model_copy(update={"problem_frame": frame})
    rehydrated = PipelineState.model_validate(state.model_dump(mode="json"))
    assert rehydrated.problem_frame is not None
    assert rehydrated.problem_frame.user_goal == "find drug targets"
    assert rehydrated.problem_frame.confidence == 0.8


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


def test_state_roundtrips_supervisor_fields(base_state: PipelineState) -> None:
    state = base_state.model_copy(
        update={
            "current_phase": "planning",
            "supervisor_call_count": 4,
            "phase_call_counts": {"scoping": 1, "planning": 2},
            "last_routing_reason": "plan submitted — execute",
            "last_assistant_prose": "We prepared a two-step plan.",
        }
    )
    rehydrated = PipelineState.model_validate(state.model_dump(mode="json"))
    assert rehydrated.current_phase == "planning"
    assert rehydrated.supervisor_call_count == 4
    assert rehydrated.phase_call_counts == {"scoping": 1, "planning": 2}
    assert rehydrated.last_routing_reason == "plan submitted — execute"
    assert rehydrated.last_assistant_prose == "We prepared a two-step plan."
