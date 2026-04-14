from __future__ import annotations

from operator import add
from typing import get_args, get_origin
from uuid import uuid4

import pytest
from pydantic import ValidationError
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)

from pathfinder.ai.agents._phase_decisions import (
    DiscoveryDecision,
    ExecutionDecision,
    PlanningDecision,
    ScopingDecision,
    VerificationDecision,
)
from pathfinder.ai.agents.state import SearchOverview
from pathfinder.ai.graph.state import (
    PHASE_NAMES,
    PhaseName,
    PipelineState,
    ProblemFrame,
)


@pytest.fixture
def base_state() -> PipelineState:
    return PipelineState(
        chat_id=uuid4(),
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
    assert base_state.message_history == []
    assert base_state.phase_decisions == {}
    assert base_state.retry_counts == {}
    assert base_state.discovered_searches == {}
    assert base_state.problem_frame is None
    assert base_state.current_phase is None


def test_state_rejects_unknown_phase_name() -> None:
    with pytest.raises(ValidationError):
        PipelineState(
            chat_id=uuid4(),
            user_id=uuid4(),
            site_id="plasmodb",
            mode="strategy",
            current_phase="bogus",  # type: ignore[arg-type]
        )


def test_message_history_uses_add_reducer() -> None:
    field_info = PipelineState.model_fields["message_history"]
    metadata = field_info.metadata
    reducer_callables = [m for m in metadata if callable(m)]
    assert add in reducer_callables, (
        "message_history must declare operator.add as its reducer "
        "so node returns concatenate rather than overwrite"
    )
    origin = get_origin(field_info.annotation)
    assert origin is list


def test_state_serializes_with_pydantic_ai_messages(base_state: PipelineState) -> None:
    request = ModelRequest(parts=[UserPromptPart(content="hi")])
    response = ModelResponse(parts=[TextPart(content="hello")])
    state = base_state.model_copy(update={"message_history": [request, response]})
    dumped = state.model_dump(mode="json")
    rehydrated = PipelineState.model_validate(dumped)
    assert len(rehydrated.message_history) == 2
    assert isinstance(rehydrated.message_history[0], ModelRequest)
    assert isinstance(rehydrated.message_history[1], ModelResponse)


def test_state_phase_decisions_roundtrip_discriminated_union(
    base_state: PipelineState,
) -> None:
    decisions: dict[PhaseName, object] = {
        "scoping": ScopingDecision(next_action="advance_to_discovery"),
        "discovery": DiscoveryDecision(next_action="advance_to_planning"),
        "planning": PlanningDecision(next_action="advance_to_execution"),
        "execution": ExecutionDecision(next_action="advance_to_verification"),
        "verification": VerificationDecision(next_action="complete"),
    }
    state = base_state.model_copy(update={"phase_decisions": decisions})
    dumped = state.model_dump(mode="json")
    rehydrated = PipelineState.model_validate(dumped)
    assert isinstance(rehydrated.phase_decisions["scoping"], ScopingDecision)
    assert isinstance(rehydrated.phase_decisions["discovery"], DiscoveryDecision)
    assert isinstance(rehydrated.phase_decisions["planning"], PlanningDecision)
    assert isinstance(rehydrated.phase_decisions["execution"], ExecutionDecision)
    assert isinstance(
        rehydrated.phase_decisions["verification"], VerificationDecision
    )


def test_state_overlapping_next_action_discriminates_by_phase(
    base_state: PipelineState,
) -> None:
    state = base_state.model_copy(
        update={
            "phase_decisions": {
                "planning": PlanningDecision(next_action="abort"),
                "execution": ExecutionDecision(next_action="abort"),
                "verification": VerificationDecision(next_action="abort"),
            }
        }
    )
    rehydrated = PipelineState.model_validate(state.model_dump(mode="json"))
    assert isinstance(rehydrated.phase_decisions["planning"], PlanningDecision)
    assert isinstance(rehydrated.phase_decisions["execution"], ExecutionDecision)
    assert isinstance(
        rehydrated.phase_decisions["verification"], VerificationDecision
    )


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
