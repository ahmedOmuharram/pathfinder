from __future__ import annotations

from langgraph.graph import END

from pathfinder.ai.agents._phase_decisions import (
    DiscoveryDecision,
    ExecutionDecision,
    PlanningDecision,
    ScopingDecision,
    VerificationDecision,
)
from pathfinder.ai.graph.state import PipelineState

EXECUTION_RETRY_BUDGET: int = 3


def route_after_scoping(state: PipelineState) -> str:
    decision = state.phase_decisions["scoping"]
    if not isinstance(decision, ScopingDecision):
        msg = f"expected ScopingDecision, got {type(decision).__name__}"
        raise TypeError(msg)
    match decision.next_action:
        case "advance_to_discovery":
            return "discovery"
        case "advance_to_planning":
            return "planning"
        case "need_more_input":
            return END


def route_after_discovery(state: PipelineState) -> str:
    decision = state.phase_decisions["discovery"]
    if not isinstance(decision, DiscoveryDecision):
        msg = f"expected DiscoveryDecision, got {type(decision).__name__}"
        raise TypeError(msg)
    match decision.next_action:
        case "advance_to_planning":
            return "planning"
        case "advance_to_execution":
            return "execution"
        case "need_more_input":
            return END


def route_after_planning(state: PipelineState) -> str:
    decision = state.phase_decisions["planning"]
    if not isinstance(decision, PlanningDecision):
        msg = f"expected PlanningDecision, got {type(decision).__name__}"
        raise TypeError(msg)
    match decision.next_action:
        case "advance_to_execution":
            return "execution"
        case "request_revision" | "abort":
            return END


def route_after_execution(state: PipelineState) -> str:
    decision = state.phase_decisions["execution"]
    if not isinstance(decision, ExecutionDecision):
        msg = f"expected ExecutionDecision, got {type(decision).__name__}"
        raise TypeError(msg)
    match decision.next_action:
        case "advance_to_verification":
            return "verification"
        case "retry":
            attempts = state.retry_counts.get("execution", 0)
            return "execution" if attempts < EXECUTION_RETRY_BUDGET else END
        case "abort":
            return END


def route_after_verification(state: PipelineState) -> str:
    decision = state.phase_decisions["verification"]
    if not isinstance(decision, VerificationDecision):
        msg = f"expected VerificationDecision, got {type(decision).__name__}"
        raise TypeError(msg)
    return END
