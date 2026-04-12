"""Structured phase-exit tools for scoping, discovery, planning, and verification."""

from pydantic import Field
from pydantic_ai import RunContext

from pathfinder.ai.orchestration.deps import AgentDeps
from pathfinder.ai.orchestration.phase_results import (
    ClarificationQuestion,
    DiscoveryResult,
    PhaseDecision,
    PlanningResult,
    ScopingResult,
    VerificationResult,
)
from pathfinder.domain.strategy.plan import PlanStatus
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.platform.tool_errors import ToolErrorPayload, tool_error


class PhaseDecisionResponse(CamelModel):
    """Tool response persisted into the transcript for a phase exit."""

    phase_decision: PhaseDecision = Field(alias="phaseDecision")


def _phase_response(record: PhaseDecision) -> PhaseDecisionResponse:
    return PhaseDecisionResponse(phaseDecision=record)


async def finish_scoping(
    ctx: RunContext[AgentDeps],
    decision: str,
    summary: str,
    questions: list[ClarificationQuestion] | None = None,
) -> PhaseDecisionResponse | ToolErrorPayload:
    """End scoping by either pausing for user input or continuing to discovery."""
    if decision not in {"ask_user", "continue_to_discovery"}:
        return tool_error(
            "INVALID_PHASE_DECISION",
            "finish_scoping decision must be 'ask_user' or 'continue_to_discovery'.",
        )

    frame = ctx.deps.problem_frame
    if frame is None:
        return tool_error(
            "MISSING_PROBLEM_FRAME",
            "Call set_problem_frame before finish_scoping.",
        )

    record = PhaseDecision(
        phase="scoping",
        decision=decision,
        summary=summary,
        questions=questions or [],
    )
    ctx.deps.scoping_result = ScopingResult(problem_frame=frame, decision=record)
    return _phase_response(record)


async def finish_discovery(
    ctx: RunContext[AgentDeps],
    decision: str,
    summary: str,
    questions: list[ClarificationQuestion] | None = None,
) -> PhaseDecisionResponse | ToolErrorPayload:
    """End discovery by either pausing for user input or continuing to planning."""
    if decision not in {"ask_user", "continue_to_planning"}:
        return tool_error(
            "INVALID_PHASE_DECISION",
            "finish_discovery decision must be 'ask_user' or 'continue_to_planning'.",
        )

    previous = ctx.deps.discovery_result or DiscoveryResult()
    record = PhaseDecision(
        phase="discovery",
        decision=decision,
        summary=summary,
        questions=questions or [],
    )
    ctx.deps.discovery_result = DiscoveryResult(
        discovered_searches=previous.discovered_searches,
        research_notes=previous.research_notes,
        intent_summary=previous.intent_summary,
        decision=record,
    )
    return _phase_response(record)


async def finish_planning(
    ctx: RunContext[AgentDeps],
    decision: str,
    summary: str,
    questions: list[ClarificationQuestion] | None = None,
) -> PhaseDecisionResponse | ToolErrorPayload:
    """End planning by either asking the user a blocking question or presenting a plan."""
    if decision not in {"ask_user", "present_plan"}:
        return tool_error(
            "INVALID_PHASE_DECISION",
            "finish_planning decision must be 'ask_user' or 'present_plan'.",
        )

    plan = ctx.deps.agent_state.active_plan
    if decision == "present_plan" and (
        plan is None or plan.status != PlanStatus.PRESENTED
    ):
        return tool_error(
            "PLAN_NOT_PRESENTED",
            "Call submit_plan before finish_planning(decision='present_plan').",
        )

    previous = ctx.deps.planning_result or PlanningResult()
    record = PhaseDecision(
        phase="planning",
        decision=decision,
        summary=summary,
        questions=questions or [],
    )
    ctx.deps.planning_result = PlanningResult(
        approved_plan=previous.approved_plan,
        questions_answered=list(previous.questions_answered),
        decision=record,
    )
    return _phase_response(record)


async def finish_verification(
    ctx: RunContext[AgentDeps],
    decision: str,
    summary: str,
    questions: list[ClarificationQuestion] | None = None,
) -> PhaseDecisionResponse | ToolErrorPayload:
    """End verification by either completing the turn or pausing for user input."""
    if decision not in {"ask_user", "complete"}:
        return tool_error(
            "INVALID_PHASE_DECISION",
            "finish_verification decision must be 'ask_user' or 'complete'.",
        )

    previous = ctx.deps.verification_result or VerificationResult()
    record = PhaseDecision(
        phase="verification",
        decision=decision,
        summary=summary,
        questions=questions or [],
    )
    ctx.deps.verification_result = VerificationResult(
        assessment=summary or previous.assessment,
        sample_record_count=previous.sample_record_count,
        enrichment_ran=previous.enrichment_ran,
        decision=record,
    )
    return _phase_response(record)
