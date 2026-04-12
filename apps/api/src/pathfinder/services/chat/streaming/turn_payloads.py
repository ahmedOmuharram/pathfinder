"""Phase and turn payload builders for streamed chat observability."""

from pydantic import Field

from pathfinder.ai.orchestration.deps import AgentDeps
from pathfinder.domain.strategy.plan import StrategyPlan
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.platform.types import JSONObject
from pathfinder.services.chat.streaming.node_streaming import TurnCounters
from pathfinder.services.chat.streaming.turn_telemetry import (
    TurnFailureContext,
    TurnLatencySummary,
    TurnRuntimeTelemetry,
    TurnTelemetryContext,
)


class RecoveryPayload(CamelModel):
    """Structured recovery event payload."""

    phase: str
    kind: str
    summary: str
    metadata: JSONObject = Field(default_factory=dict)
    recorded_at: str


class PlanSummaryPayload(CamelModel):
    """Summary of a StrategyPlan for observability payloads."""

    plan_id: str
    status: str
    step_count: int
    question_count: int
    answered_question_count: int
    uncertainty_count: int
    updated_at: str
    step_status_counts: dict[str, int]


class ScopingPhaseResult(CamelModel):
    decision: str | None
    decision_summary: str | None
    question_count: int
    organism_scope: str | None = None
    record_type: str | None = None
    ready_for_wdk_discovery: bool | None = None
    confidence: float | None = None
    blocking_question_count: int = 0
    optional_question_count: int = 0
    research_note_count: int = 0
    recoveries: list[RecoveryPayload] = Field(default_factory=list)


class DiscoveryPhaseResult(CamelModel):
    decision: str | None
    decision_summary: str | None
    question_count: int
    discovered_search_count: int
    discovered_search_names: list[str]
    intent_summary: str = ""
    research_notes: str = ""
    recoveries: list[RecoveryPayload] = Field(default_factory=list)


class PlanningPhaseResult(CamelModel):
    decision: str | None
    decision_summary: str | None
    question_count: int
    questions_answered_count: int
    plan: PlanSummaryPayload | None = None
    recoveries: list[RecoveryPayload] = Field(default_factory=list)


class ExecutionPhaseResult(CamelModel):
    plan: PlanSummaryPayload | None = None
    wdk_strategy_id: int | None = None
    step_result_count: int = 0
    error_count: int = 0
    recoveries: list[RecoveryPayload] = Field(default_factory=list)


class VerificationPhaseResult(CamelModel):
    decision: str | None
    decision_summary: str | None
    question_count: int
    assessment: str = ""
    sample_record_count: int = 0
    enrichment_ran: bool = False
    recoveries: list[RecoveryPayload] = Field(default_factory=list)


PhaseResult = (
    ScopingPhaseResult
    | DiscoveryPhaseResult
    | PlanningPhaseResult
    | ExecutionPhaseResult
    | VerificationPhaseResult
)


class PhaseTimingPayload(CamelModel):
    phase: str
    status: str
    attempt: int
    emitted_at: str
    phase_started_at: str | None = None
    phase_completed_at: str | None = None
    duration_ms: int | None = None


class TurnUsagePayload(CamelModel):
    prompt_tokens: int
    completion_tokens: int
    cached_tokens: int
    llm_call_count: int
    tool_call_count: int
    estimated_cost_usd: float | None = None


class TurnPlanActionPayload(CamelModel):
    action: str
    plan_id: str | None = None
    source_trace_id: str | None = None
    source_message_group_id: str | None = None
    source: str | None = None
    answered_question_ids: list[str] = Field(default_factory=list)
    edited_params: list[str] = Field(default_factory=list)
    approval_wait_ms: int | None = None
    presented_at: str | None = None
    approved_at: str | None = None


class TurnPhaseResults(CamelModel):
    scoping: ScopingPhaseResult | None = None
    discovery: DiscoveryPhaseResult | None = None
    planning: PlanningPhaseResult | None = None
    execution: ExecutionPhaseResult | None = None
    verification: VerificationPhaseResult | None = None


class TurnOutputPayload(CamelModel):
    outcome: str
    assistant_message: str | None = None
    latency: TurnLatencySummary
    usage: TurnUsagePayload
    plan_action: TurnPlanActionPayload | None = None
    active_plan: PlanSummaryPayload | None = None
    phase_results: TurnPhaseResults = Field(default_factory=TurnPhaseResults)
    phases: list[PhaseTimingPayload] = Field(default_factory=list)
    recoveries: list[RecoveryPayload] = Field(default_factory=list)
    failure: TurnFailureContext | None = None
    total_duration_ms: int


def _plan_summary(plan: StrategyPlan | None) -> PlanSummaryPayload | None:
    if plan is None:
        return None
    step_status_counts: dict[str, int] = {}
    for step in plan.steps:
        key = step.status.value
        step_status_counts[key] = step_status_counts.get(key, 0) + 1
    answered_questions = sum(1 for question in plan.questions if question.answer is not None)
    return PlanSummaryPayload(
        plan_id=plan.id,
        status=plan.status.value,
        step_count=len(plan.steps),
        question_count=len(plan.questions),
        answered_question_count=answered_questions,
        uncertainty_count=len(plan.uncertainties),
        updated_at=plan.updated_at.isoformat(),
        step_status_counts=step_status_counts,
    )


def _decision_summary(decision: object | None) -> tuple[str | None, str | None, int]:
    if decision is None:
        return None, None, 0
    return (
        getattr(decision, "decision", None),
        getattr(decision, "summary", None),
        len(getattr(decision, "questions", [])),
    )


def _recoveries_from_runtime(
    runtime: TurnRuntimeTelemetry | None,
    phase: str,
) -> list[RecoveryPayload]:
    if runtime is None:
        return []
    return [
        RecoveryPayload.model_validate(payload)
        for payload in runtime.recoveries_for_phase(phase)
    ]


def _scoping_phase_result_summary(
    deps: AgentDeps,
    *,
    recoveries: list[RecoveryPayload],
) -> ScopingPhaseResult | None:
    result = deps.scoping_result
    frame = deps.problem_frame or (result.problem_frame if result is not None else None)
    if frame is None and result is None and not recoveries:
        return None
    decision_name, decision_summary, question_count = _decision_summary(
        result.decision if result is not None else None
    )
    return ScopingPhaseResult(
        decision=decision_name,
        decision_summary=decision_summary,
        question_count=question_count,
        organism_scope=frame.organism_scope if frame is not None else None,
        record_type=frame.record_type if frame is not None else None,
        ready_for_wdk_discovery=(
            frame.ready_for_wdk_discovery if frame is not None else None
        ),
        confidence=frame.confidence if frame is not None else None,
        blocking_question_count=len(frame.blocking_questions) if frame is not None else 0,
        optional_question_count=len(frame.optional_questions) if frame is not None else 0,
        research_note_count=len(frame.research_notes) if frame is not None else 0,
        recoveries=recoveries,
    )


def _discovery_phase_result_summary(
    deps: AgentDeps,
    *,
    recoveries: list[RecoveryPayload],
) -> DiscoveryPhaseResult | None:
    result = deps.discovery_result
    discovered_searches = (
        result.discovered_searches
        if result is not None and result.discovered_searches
        else deps.agent_state.discovered_searches
    )
    if result is None and not discovered_searches and not recoveries:
        return None
    decision_name, decision_summary, question_count = _decision_summary(
        result.decision if result is not None else None
    )
    search_names = sorted(discovered_searches)
    return DiscoveryPhaseResult(
        decision=decision_name,
        decision_summary=decision_summary,
        question_count=question_count,
        discovered_search_count=len(search_names),
        discovered_search_names=search_names,
        intent_summary=result.intent_summary if result is not None else "",
        research_notes=result.research_notes if result is not None else "",
        recoveries=recoveries,
    )


def _planning_phase_result_summary(
    deps: AgentDeps,
    *,
    recoveries: list[RecoveryPayload],
) -> PlanningPhaseResult | None:
    result = deps.planning_result
    plan = deps.agent_state.active_plan
    if result is None and plan is None and not recoveries:
        return None
    decision_name, decision_summary, question_count = _decision_summary(
        result.decision if result is not None else None
    )
    return PlanningPhaseResult(
        decision=decision_name,
        decision_summary=decision_summary,
        question_count=question_count,
        questions_answered_count=len(result.questions_answered) if result is not None else 0,
        plan=_plan_summary(plan),
        recoveries=recoveries,
    )


def _execution_phase_result_summary(
    deps: AgentDeps,
    *,
    recoveries: list[RecoveryPayload],
) -> ExecutionPhaseResult | None:
    plan = deps.agent_state.active_plan
    execution_result = deps.execution_result
    if plan is None and execution_result is None and not recoveries:
        return None
    return ExecutionPhaseResult(
        plan=_plan_summary(plan),
        wdk_strategy_id=(
            execution_result.wdk_strategy_id if execution_result is not None else None
        ),
        step_result_count=(
            len(execution_result.step_results) if execution_result is not None else 0
        ),
        error_count=len(execution_result.errors) if execution_result is not None else 0,
        recoveries=recoveries,
    )


def _verification_phase_result_summary(
    deps: AgentDeps,
    *,
    recoveries: list[RecoveryPayload],
) -> VerificationPhaseResult | None:
    result = deps.verification_result
    if result is None and not recoveries:
        return None
    decision_name, decision_summary, question_count = _decision_summary(
        result.decision if result is not None else None
    )
    return VerificationPhaseResult(
        decision=decision_name,
        decision_summary=decision_summary,
        question_count=question_count,
        assessment=result.assessment if result is not None else "",
        sample_record_count=result.sample_record_count if result is not None else 0,
        enrichment_ran=result.enrichment_ran if result is not None else False,
        recoveries=recoveries,
    )


def phase_result_summary(
    deps: AgentDeps,
    phase: str,
    *,
    runtime: TurnRuntimeTelemetry | None = None,
) -> PhaseResult | None:
    """Return a phase-specific structured summary for observability."""
    recoveries = _recoveries_from_runtime(runtime, phase)
    if phase == "scoping":
        return _scoping_phase_result_summary(deps, recoveries=recoveries)
    if phase == "discovery":
        return _discovery_phase_result_summary(deps, recoveries=recoveries)
    if phase == "planning":
        return _planning_phase_result_summary(deps, recoveries=recoveries)
    if phase == "execution":
        return _execution_phase_result_summary(deps, recoveries=recoveries)
    if phase == "verification":
        return _verification_phase_result_summary(deps, recoveries=recoveries)
    return None


def _plan_action_payload(turn_ctx: TurnTelemetryContext) -> TurnPlanActionPayload | None:
    plan_action = turn_ctx.deps.plan_action
    if plan_action is None:
        return None
    return TurnPlanActionPayload(
        action=plan_action.action,
        plan_id=plan_action.plan_id,
        source_trace_id=plan_action.source_trace_id,
        source_message_group_id=plan_action.source_message_group_id,
        source=plan_action.source,
        answered_question_ids=list(plan_action.answered_question_ids),
        edited_params=list(plan_action.edited_params),
        approval_wait_ms=plan_action.approval_wait_ms,
        presented_at=(
            plan_action.presented_at.isoformat()
            if plan_action.presented_at is not None
            else None
        ),
        approved_at=(
            plan_action.approved_at.isoformat()
            if plan_action.approved_at is not None
            else None
        ),
    )


def _turn_phase_results(turn_ctx: TurnTelemetryContext) -> TurnPhaseResults:
    deps = turn_ctx.deps
    runtime = turn_ctx.runtime
    return TurnPhaseResults(
        scoping=_scoping_phase_result_summary(
            deps, recoveries=_recoveries_from_runtime(runtime, "scoping")
        ),
        discovery=_discovery_phase_result_summary(
            deps, recoveries=_recoveries_from_runtime(runtime, "discovery")
        ),
        planning=_planning_phase_result_summary(
            deps, recoveries=_recoveries_from_runtime(runtime, "planning")
        ),
        execution=_execution_phase_result_summary(
            deps, recoveries=_recoveries_from_runtime(runtime, "execution")
        ),
        verification=_verification_phase_result_summary(
            deps, recoveries=_recoveries_from_runtime(runtime, "verification")
        ),
    )


def _turn_phase_timings(turn_ctx: TurnTelemetryContext) -> list[PhaseTimingPayload]:
    return [
        PhaseTimingPayload(
            phase=snapshot.phase,
            status=snapshot.status,
            attempt=snapshot.attempt,
            emitted_at=snapshot.emitted_at,
            phase_started_at=snapshot.phase_started_at,
            phase_completed_at=snapshot.phase_completed_at,
            duration_ms=snapshot.duration_ms,
        )
        for snapshot in turn_ctx.phase_timings.terminal_history()
    ]


def _turn_recoveries(turn_ctx: TurnTelemetryContext) -> list[RecoveryPayload]:
    return [
        RecoveryPayload(
            phase=recovery.phase,
            kind=recovery.kind,
            summary=recovery.summary,
            metadata=recovery.metadata,
            recorded_at=recovery.recorded_at,
        )
        for recovery in turn_ctx.runtime.recoveries
    ]


def build_turn_output_payload(
    turn_ctx: TurnTelemetryContext,
    counters: TurnCounters,
    *,
    outcome: str,
    total_duration_ms: int,
    estimated_cost: float | None,
    failure_context: TurnFailureContext | None = None,
) -> TurnOutputPayload:
    """Build a structured root trace output payload for Langfuse."""
    return TurnOutputPayload(
        outcome=outcome,
        assistant_message=counters.last_assistant_message,
        latency=turn_ctx.runtime.latency_summary(
            turn_started_monotonic=turn_ctx.turn_started_monotonic,
            phase_timings=turn_ctx.phase_timings,
        ),
        usage=TurnUsagePayload(
            prompt_tokens=counters.input_tokens,
            completion_tokens=counters.output_tokens,
            cached_tokens=counters.cache_read_tokens,
            llm_call_count=counters.llm_call_count,
            tool_call_count=counters.tool_call_count,
            estimated_cost_usd=estimated_cost,
        ),
        plan_action=_plan_action_payload(turn_ctx),
        active_plan=_plan_summary(turn_ctx.deps.agent_state.active_plan),
        phase_results=_turn_phase_results(turn_ctx),
        phases=_turn_phase_timings(turn_ctx),
        recoveries=_turn_recoveries(turn_ctx),
        failure=failure_context,
        total_duration_ms=total_duration_ms,
    )
