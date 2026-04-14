from __future__ import annotations

from uuid import uuid4

import pytest
from langgraph.graph import END

from pathfinder.ai.agents._phase_decisions import (
    DiscoveryDecision,
    ExecutionDecision,
    PlanningDecision,
    ScopingDecision,
    VerificationDecision,
)
from pathfinder.ai.graph.router import (
    EXECUTION_RETRY_BUDGET,
    route_after_discovery,
    route_after_execution,
    route_after_planning,
    route_after_scoping,
    route_after_verification,
)
from pathfinder.ai.graph.state import PipelineState


def _state(**overrides: object) -> PipelineState:
    base = PipelineState(
        chat_id=uuid4(),
        user_id=uuid4(),
        site_id="plasmodb",
        mode="strategy",
    )
    return base.model_copy(update=dict(overrides))


def test_route_after_scoping_advance_to_discovery() -> None:
    state = _state(
        phase_decisions={"scoping": ScopingDecision(next_action="advance_to_discovery")}
    )
    assert route_after_scoping(state) == "discovery"


def test_route_after_scoping_advance_to_planning_skips_discovery() -> None:
    state = _state(
        phase_decisions={"scoping": ScopingDecision(next_action="advance_to_planning")}
    )
    assert route_after_scoping(state) == "planning"


def test_route_after_scoping_need_more_input_ends() -> None:
    state = _state(
        phase_decisions={"scoping": ScopingDecision(next_action="need_more_input")}
    )
    assert route_after_scoping(state) == END


def test_route_after_discovery_advance_to_planning() -> None:
    state = _state(
        phase_decisions={
            "discovery": DiscoveryDecision(next_action="advance_to_planning")
        }
    )
    assert route_after_discovery(state) == "planning"


def test_route_after_discovery_advance_to_execution_skips_planning() -> None:
    state = _state(
        phase_decisions={
            "discovery": DiscoveryDecision(next_action="advance_to_execution")
        }
    )
    assert route_after_discovery(state) == "execution"


def test_route_after_discovery_need_more_input_ends() -> None:
    state = _state(
        phase_decisions={
            "discovery": DiscoveryDecision(next_action="need_more_input")
        }
    )
    assert route_after_discovery(state) == END


def test_route_after_planning_advance_to_execution() -> None:
    state = _state(
        phase_decisions={
            "planning": PlanningDecision(next_action="advance_to_execution")
        }
    )
    assert route_after_planning(state) == "execution"


def test_route_after_planning_request_revision_ends_turn() -> None:
    state = _state(
        phase_decisions={
            "planning": PlanningDecision(next_action="request_revision")
        }
    )
    assert route_after_planning(state) == END


def test_route_after_planning_abort_ends() -> None:
    state = _state(
        phase_decisions={"planning": PlanningDecision(next_action="abort")}
    )
    assert route_after_planning(state) == END


def test_route_after_execution_advance_to_verification() -> None:
    state = _state(
        phase_decisions={
            "execution": ExecutionDecision(next_action="advance_to_verification")
        }
    )
    assert route_after_execution(state) == "verification"


def test_route_after_execution_retry_loops_when_budget_remains() -> None:
    state = _state(
        phase_decisions={"execution": ExecutionDecision(next_action="retry")},
        retry_counts={"execution": 0},
    )
    assert route_after_execution(state) == "execution"


def test_route_after_execution_retry_ends_when_budget_exhausted() -> None:
    state = _state(
        phase_decisions={"execution": ExecutionDecision(next_action="retry")},
        retry_counts={"execution": EXECUTION_RETRY_BUDGET},
    )
    assert route_after_execution(state) == END


def test_route_after_execution_abort_ends() -> None:
    state = _state(
        phase_decisions={"execution": ExecutionDecision(next_action="abort")}
    )
    assert route_after_execution(state) == END


@pytest.mark.parametrize(
    "action",
    ["complete", "retry_execution", "abort"],
)
def test_route_after_verification_always_ends(action: str) -> None:
    state = _state(
        phase_decisions={
            "verification": VerificationDecision(next_action=action),  # type: ignore[arg-type]
        }
    )
    assert route_after_verification(state) == END


def test_route_after_scoping_raises_when_decision_missing() -> None:
    state = _state()
    with pytest.raises(KeyError):
        route_after_scoping(state)
