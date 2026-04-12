"""Shared recovery helpers for phases that drift without finish_* tools."""

from __future__ import annotations

from collections.abc import Callable

from pathfinder.ai.orchestration.deps import AgentDeps
from pathfinder.ai.orchestration.phase_results import (
    DiscoveryResult,
    PhaseDecision,
    PhaseName,
    PlanningResult,
    ScopingResult,
    VerificationResult,
)
from pathfinder.domain.strategy.plan import PlanStatus
from pathfinder.platform.logging import get_logger
from pathfinder.platform.types import JSONObject

logger = get_logger(__name__)

type RecoveryRecorder = Callable[[str, str, str, JSONObject | None], None] | None

_INPUT_MARKERS = (
    "would you like",
    "do you want",
    "could you",
    "can you",
    "please confirm",
    "please clarify",
    "let me know",
    "tell me whether",
)


def _record_phase_recovery(
    *,
    phase: str,
    kind: str,
    summary: str,
    metadata: JSONObject,
    record_recovery: RecoveryRecorder,
) -> None:
    logger.warning(
        "Recovered missing phase finish tool",
        phase=phase,
        recovery_kind=kind,
        recovery_summary=summary,
        **metadata,
    )
    if record_recovery is not None:
        record_recovery(phase, kind, summary, metadata)


def _assistant_requested_user_input(assistant_text: str) -> bool:
    normalized = assistant_text.strip().lower()
    if normalized == "":
        return False
    if normalized.endswith("?"):
        return True
    return any(marker in normalized for marker in _INPUT_MARKERS)


def _persist_scoping_decision(
    deps: AgentDeps,
    decision: PhaseDecision,
) -> None:
    frame = deps.problem_frame
    if frame is None and deps.scoping_result is not None:
        frame = deps.scoping_result.problem_frame
    deps.problem_frame = frame
    deps.scoping_result = ScopingResult(problem_frame=frame, decision=decision)


def _persist_discovery_decision(
    deps: AgentDeps,
    decision: PhaseDecision,
) -> None:
    previous = deps.discovery_result or DiscoveryResult()
    deps.discovery_result = DiscoveryResult(
        discovered_searches=previous.discovered_searches
        or dict(deps.agent_state.discovered_searches),
        research_notes=previous.research_notes,
        intent_summary=previous.intent_summary,
        decision=decision,
    )


def _persist_planning_decision(
    deps: AgentDeps,
    decision: PhaseDecision,
) -> None:
    previous = deps.planning_result or PlanningResult()
    deps.planning_result = PlanningResult(
        approved_plan=previous.approved_plan,
        questions_answered=list(previous.questions_answered),
        decision=decision,
    )


def _persist_verification_decision(
    deps: AgentDeps,
    decision: PhaseDecision,
    *,
    assistant_text: str,
) -> None:
    previous = deps.verification_result or VerificationResult()
    deps.verification_result = VerificationResult(
        assessment=previous.assessment or assistant_text.strip(),
        sample_record_count=previous.sample_record_count,
        enrichment_ran=previous.enrichment_ran,
        decision=decision,
    )


def _recover_scoping_from_problem_frame(
    deps: AgentDeps,
    *,
    record_recovery: RecoveryRecorder,
) -> PhaseDecision | None:
    frame = deps.problem_frame
    if frame is None and deps.scoping_result is not None:
        frame = deps.scoping_result.problem_frame
    if frame is None:
        return None

    should_pause = bool(frame.blocking_questions) or not frame.ready_for_wdk_discovery
    decision = PhaseDecision(
        phase="scoping",
        decision="ask_user" if should_pause else "continue_to_discovery",
        summary=(
            "Recovered missing finish_scoping from saved problem frame."
            if not should_pause
            else (
                "Recovered missing finish_scoping and paused for user input from "
                "the saved problem frame."
            )
        ),
        questions=list(frame.blocking_questions),
    )
    _persist_scoping_decision(deps, decision)
    _record_phase_recovery(
        phase="scoping",
        kind="missing_finish_scoping",
        summary=decision.summary,
        metadata={
            "readyForWdkDiscovery": frame.ready_for_wdk_discovery,
            "blockingQuestionCount": len(frame.blocking_questions),
            "recoveredDecision": decision.decision,
        },
        record_recovery=record_recovery,
    )
    return decision


def _recover_discovery_from_state(
    deps: AgentDeps,
    *,
    record_recovery: RecoveryRecorder,
) -> PhaseDecision | None:
    previous = deps.discovery_result or DiscoveryResult()
    discovered_searches = previous.discovered_searches or dict(
        deps.agent_state.discovered_searches
    )
    if (
        not discovered_searches
        and previous.research_notes.strip() == ""
        and previous.intent_summary.strip() == ""
    ):
        return None

    decision = PhaseDecision(
        phase="discovery",
        decision="continue_to_planning",
        summary="Recovered missing finish_discovery from discovered catalog context.",
    )
    _persist_discovery_decision(deps, decision)
    _record_phase_recovery(
        phase="discovery",
        kind="missing_finish_discovery",
        summary=decision.summary,
        metadata={
            "discoveredSearchCount": len(discovered_searches),
            "hasResearchNotes": previous.research_notes.strip() != "",
            "hasIntentSummary": previous.intent_summary.strip() != "",
            "recoveredDecision": decision.decision,
        },
        record_recovery=record_recovery,
    )
    return decision


def _recover_planning_from_presented_plan(
    deps: AgentDeps,
    *,
    record_recovery: RecoveryRecorder,
) -> PhaseDecision | None:
    plan = deps.agent_state.active_plan
    if plan is None or plan.status != PlanStatus.PRESENTED:
        return None

    decision = PhaseDecision(
        phase="planning",
        decision="present_plan",
        summary="Recovered missing finish_planning from presented plan state.",
    )
    _persist_planning_decision(deps, decision)
    _record_phase_recovery(
        phase="planning",
        kind="missing_finish_planning",
        summary=decision.summary,
        metadata={
            "planId": plan.id,
            "planStatus": plan.status.value,
            "stepCount": len(plan.steps),
            "recoveredDecision": decision.decision,
        },
        record_recovery=record_recovery,
    )
    return decision


def _recover_verification_from_summary(
    deps: AgentDeps,
    *,
    assistant_text: str,
    record_recovery: RecoveryRecorder,
) -> PhaseDecision | None:
    previous = deps.verification_result or VerificationResult()
    assessment = previous.assessment or assistant_text.strip()
    if (
        assessment == ""
        and previous.sample_record_count <= 0
        and not previous.enrichment_ran
    ):
        return None

    decision = PhaseDecision(
        phase="verification",
        decision="complete",
        summary=assessment or "Recovered missing finish_verification.",
    )
    _persist_verification_decision(deps, decision, assistant_text=assistant_text)
    _record_phase_recovery(
        phase="verification",
        kind="missing_finish_verification",
        summary="Recovered missing finish_verification from verification output.",
        metadata={
            "hasAssessment": assessment != "",
            "sampleRecordCount": previous.sample_record_count,
            "enrichmentRan": previous.enrichment_ran,
            "recoveredDecision": decision.decision,
        },
        record_recovery=record_recovery,
    )
    return decision


def _recover_pause_from_assistant_text(
    deps: AgentDeps,
    phase: PhaseName,
    *,
    assistant_text: str,
    record_recovery: RecoveryRecorder,
) -> PhaseDecision | None:
    if not _assistant_requested_user_input(assistant_text):
        return None

    summary = assistant_text.strip()
    decision = PhaseDecision(
        phase=phase,
        decision="ask_user",
        summary=summary,
    )
    if phase == "scoping":
        _persist_scoping_decision(deps, decision)
    elif phase == "discovery":
        _persist_discovery_decision(deps, decision)
    elif phase == "planning":
        _persist_planning_decision(deps, decision)
    elif phase == "verification":
        _persist_verification_decision(deps, decision, assistant_text=assistant_text)
    else:
        return None

    _record_phase_recovery(
        phase=phase,
        kind=f"missing_finish_{phase}",
        summary=f"Recovered missing finish_{phase} by pausing on assistant question text.",
        metadata={
            "recoveredDecision": decision.decision,
            "assistantQuestionDetected": True,
            "assistantTextPreview": assistant_text[:240],
        },
        record_recovery=record_recovery,
    )
    return decision


def recover_missing_phase_decision(
    deps: AgentDeps,
    phase: PhaseName,
    *,
    assistant_text: str,
    record_recovery: RecoveryRecorder,
) -> PhaseDecision | None:
    """Recover a missing finish_* decision when downstream state is sufficient."""
    recovered: PhaseDecision | None = None
    if phase == "scoping":
        recovered = _recover_scoping_from_problem_frame(
            deps,
            record_recovery=record_recovery,
        )
        if recovered is None:
            recovered = _recover_pause_from_assistant_text(
                deps,
                phase,
                assistant_text=assistant_text,
                record_recovery=record_recovery,
            )
    elif phase == "discovery":
        recovered = _recover_pause_from_assistant_text(
            deps,
            phase,
            assistant_text=assistant_text,
            record_recovery=record_recovery,
        )
        if recovered is None:
            recovered = _recover_discovery_from_state(
                deps,
                record_recovery=record_recovery,
            )
    elif phase == "planning":
        recovered = _recover_planning_from_presented_plan(
            deps,
            record_recovery=record_recovery,
        )
        if recovered is None:
            recovered = _recover_pause_from_assistant_text(
                deps,
                phase,
                assistant_text=assistant_text,
                record_recovery=record_recovery,
            )
    elif phase == "verification":
        recovered = _recover_pause_from_assistant_text(
            deps,
            phase,
            assistant_text=assistant_text,
            record_recovery=record_recovery,
        )
        if recovered is None:
            recovered = _recover_verification_from_summary(
                deps,
                assistant_text=assistant_text,
                record_recovery=record_recovery,
            )
    return recovered
