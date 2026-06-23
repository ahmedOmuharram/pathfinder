from __future__ import annotations

from typing import Literal

from pathfinder.ai.agents.state import ParamVocabSnapshot, SearchOverview
from pathfinder.ai.graph.state import PipelineState
from pathfinder.ai.lead.deltas import OpenSlot
from pathfinder.ai.lead.intent import IntentClassification, UserIntent
from pathfinder.ai.lead.ledger import (
    BuildSection,
    ConstraintSection,
    DiscoverySection,
    FrameSection,
    InvestigationLedger,
    PlanSection,
    RecoveryKind,
    SearchFitReport,
    VerificationSection,
)
from pathfinder.domain.strategy.build_outcome import (
    BuildOutcome,
    StepPushFailure,
)
from pathfinder.domain.strategy.constraints import (
    ground_against_plan,
    merge_constraints,
    provisional_constraints,
)
from pathfinder.domain.strategy.plan import (
    ParamStatus,
    PlannedStep,
    PlanStatus,
    StrategyPlan,
)

_TRANSIENT_MARKERS: frozenset[str] = frozenset(
    {
        "5xx",
        "503",
        "504",
        "502",
        "timeout",
        "timed out",
        "connection",
        "network",
    }
)
_VOCAB_MARKERS: frozenset[str] = frozenset(
    {
        "vocab",
        "validoptions",
        "valid options",
        "parameter",
        "param",
        "value",
    }
)
_SEARCH_INVALID_MARKERS: frozenset[str] = frozenset(
    {
        "unknown search",
        "invalid search",
        "search not found",
    }
)
_MIN_TERM_LEN: int = 3
_MIN_SHARED_TERMS_FOR_INTENT_MATCH: int = 3


def derive_ledger(
    state: PipelineState,
    intent: UserIntent | None,
) -> InvestigationLedger:
    """Pure derivation of the Ledger from PipelineState + the latest intent.

    No I/O. The Lead calls this on every turn. Sub-agents do NOT call it —
    they receive scoped slices via typed work orders from the Lead.
    """
    frame_section = _derive_frame_section(state, intent)
    discovery_section = _derive_discovery_section(state, intent)
    plan_section = _derive_plan_section(state)
    build_section = _derive_build_section(state)
    verification_section = _derive_verification_section(state)
    constraint_section = _derive_constraint_section(state, intent)

    return InvestigationLedger(
        user_intent=intent,
        frame=frame_section,
        discovery=discovery_section,
        plan=plan_section,
        build=build_section,
        verification=verification_section,
        constraints=constraint_section,
    )


def _derive_constraint_section(
    state: PipelineState, intent: UserIntent | None
) -> ConstraintSection:
    plan = state.active_plan
    provisional = state.problem_frame.constraints if state.problem_frame else []
    explicit = intent.explicit_constraints if intent else []
    merged = merge_constraints(provisional, explicit)
    if not merged:
        return ConstraintSection()
    if plan is None:
        return ConstraintSection(grounded=provisional_constraints(merged))
    return ConstraintSection(grounded=ground_against_plan(merged, plan))


def _derive_frame_section(
    state: PipelineState,
    intent: UserIntent | None,
) -> FrameSection:
    frame = state.problem_frame
    if frame is None:
        return FrameSection(frame=None, matches_current_intent=False)

    # A pending re-scope (user just answered scoping's blocking questions)
    # forces frame.needed True so scoping re-runs and folds the answer in —
    # but the frame stays so scoping keeps its memory.
    matches = not state.rescope_requested and _frame_matches_intent(
        frame.user_goal, intent
    )
    return FrameSection(
        frame=frame,
        matches_current_intent=matches,
        blocking_questions_unanswered=list(frame.blocking_questions),
    )


def _frame_matches_intent(frame_goal: str, intent: UserIntent | None) -> bool:
    """Heuristic: does the existing frame describe what the user is asking now?

    True when there is no intent (no new user message this turn — frame
    carries over) or the intent is a continuation (approvals, slot answers,
    follow-ups) that does not change the goal. False on a fresh
    NEW_STRATEGY message that doesn't textually overlap the existing
    frame's goal.
    """
    if intent is None:
        return True
    continuation = {
        IntentClassification.APPROVAL,
        IntentClassification.DENIAL,
        IntentClassification.SLOT_ANSWER,
        IntentClassification.CLARIFICATION_RESPONSE,
        IntentClassification.FOLLOW_UP_QUESTION,
    }
    if intent.classification in continuation:
        return True
    if not frame_goal.strip() or not intent.inferred_goal.strip():
        return False
    a = frame_goal.casefold()
    b = intent.inferred_goal.casefold()
    return a in b or b in a or _shared_terms(a, b) >= _MIN_SHARED_TERMS_FOR_INTENT_MATCH


def _shared_terms(a: str, b: str) -> int:
    a_words = {w for w in a.split() if len(w) > _MIN_TERM_LEN}
    b_words = {w for w in b.split() if len(w) > _MIN_TERM_LEN}
    return len(a_words & b_words)


def _derive_discovery_section(
    state: PipelineState,
    intent: UserIntent | None,
) -> DiscoverySection:
    selections = dict(state.discovered_searches)
    selected_count = sum(
        1 for ov in selections.values() if ov.selection_status == "selected"
    )
    rejected_count = sum(
        1 for ov in selections.values() if ov.selection_status == "rejected"
    )
    fit_reports = [_fit_report(ov, intent) for ov in selections.values()]
    intent_satisfied, intent_gap = _intent_satisfaction(fit_reports, intent)
    return DiscoverySection(
        selections=selections,
        fit_reports=fit_reports,
        selected_count=selected_count,
        rejected_count=rejected_count,
        intent_satisfied=intent_satisfied,
        intent_gap=intent_gap,
    )


def _fit_report(
    overview: SearchOverview,
    intent: UserIntent | None,
) -> SearchFitReport:
    sides = (
        list(intent.differential_sides)
        if intent is not None and intent.is_differential
        else []
    )
    coverage = {side: _vocab_covers_side(overview, side) for side in sides}
    unmatched = [side for side, covered in coverage.items() if not covered]
    return SearchFitReport(
        search_name=overview.search_name,
        display_name=overview.display_name,
        selection_status=overview.selection_status,
        intent_sides_covered=coverage,
        intent_sides_unmatched=unmatched,
        confidence=overview.confidence,
        rationale=overview.rationale,
        selection_reason=overview.selection_reason,
    )


def _vocab_covers_side(overview: SearchOverview, side: str) -> bool:
    needle = side.casefold().strip()
    if not needle:
        return True
    for snap in overview.param_vocab.values():
        if _snapshot_matches(snap, needle):
            return True
    return False


def _snapshot_matches(snap: ParamVocabSnapshot, needle: str) -> bool:
    if snap.allowed_values:
        for entry in snap.allowed_values:
            if needle in entry.value.casefold() or needle in entry.display.casefold():
                return True
    tree = snap.allowed_values_tree
    return tree is not None and needle in tree.casefold()


def _intent_satisfaction(
    reports: list[SearchFitReport],
    intent: UserIntent | None,
) -> tuple[bool, str | None]:
    if intent is None or not intent.is_differential:
        if not reports:
            return False, None
        any_selected = any(r.selection_status == "selected" for r in reports)
        return any_selected, None
    selected = [r for r in reports if r.selection_status == "selected"]
    if not selected:
        return False, "no searches selected yet"
    fully_covering = [r for r in selected if not r.intent_sides_unmatched]
    if fully_covering:
        return True, None
    union_unmatched: set[str] = set()
    for r in selected:
        union_unmatched.update(r.intent_sides_unmatched)
    gap = (
        f"selected searches' sample vocab does not include: "
        f"{', '.join(sorted(union_unmatched))}"
    )
    return False, gap


def open_user_input_slots(plan: StrategyPlan) -> list[OpenSlot]:
    """The plan's unfilled NEEDS_USER_INPUT slots — what the user must answer
    alongside (or instead of) a plain plan approval."""
    return _open_slots(plan, ParamStatus.NEEDS_USER_INPUT)


def _derive_plan_section(state: PipelineState) -> PlanSection:
    plan = state.active_plan
    if plan is None:
        return PlanSection()
    user_slots = open_user_input_slots(plan)
    discovery_slots = _open_slots(plan, ParamStatus.NEEDS_DISCOVERY)
    approved = plan.status == PlanStatus.APPROVED
    return PlanSection(
        plan=plan,
        open_user_input_slots=user_slots,
        open_discovery_slots=discovery_slots,
        approved=approved,
        last_denial_message=None if approved else _latest_denial_message(state),
    )


def _latest_denial_message(state: PipelineState) -> str | None:
    """The reason from the most recent denied plan approval, if any."""
    reason: str | None = None
    for response in state.approval_responses.values():
        if not response.approved and response.reason:
            reason = response.reason
    return reason


_PARAM_STATUS_TO_SLOT_LABEL: dict[
    ParamStatus,
    Literal["needs_user_input", "needs_discovery"],
] = {
    ParamStatus.NEEDS_USER_INPUT: "needs_user_input",
    ParamStatus.NEEDS_DISCOVERY: "needs_discovery",
}


def _open_slots(
    plan: StrategyPlan,
    status: ParamStatus,
) -> list[OpenSlot]:
    label = _PARAM_STATUS_TO_SLOT_LABEL[status]
    questions_by_key: dict[tuple[str, str], str] = {}
    for q in plan.questions:
        if q.related_step is not None and q.related_param is not None:
            questions_by_key[(q.related_step, q.related_param)] = q.question
    out: list[OpenSlot] = []
    for step in plan.steps:
        out.extend(_step_open_slots(step, status, label, questions_by_key))
    return out


def _step_open_slots(
    step: PlannedStep,
    status: ParamStatus,
    label: Literal["needs_user_input", "needs_discovery"],
    questions_by_key: dict[tuple[str, str], str],
) -> list[OpenSlot]:
    out: list[OpenSlot] = []
    for p in step.parameters:
        if p.status != status:
            continue
        question_text = questions_by_key.get((step.id, p.name), "")
        out.append(
            OpenSlot(
                step_id=step.id,
                param_name=p.name,
                status=label,
                question=question_text,
            ),
        )
    return out


def _derive_build_section(state: PipelineState) -> BuildSection:
    outcome = state.last_build_outcome
    if outcome is None:
        return BuildSection()
    failed_count = len(outcome.failed_steps)
    skipped_count = len(outcome.skipped_step_ids)
    zero_steps = list(outcome.zero_step_ids)
    needs_recovery = bool(failed_count or skipped_count or zero_steps)
    return BuildSection(
        outcome=outcome,
        pushed_count=len(outcome.pushed_step_ids),
        failed_count=failed_count,
        skipped_count=skipped_count,
        zero_result_steps=zero_steps,
        needs_recovery=needs_recovery,
        recovery_kind=_recovery_kind(outcome),
    )


def _recovery_kind(outcome: BuildOutcome) -> RecoveryKind:
    if not outcome.failed_steps and not outcome.skipped_step_ids:
        if outcome.zero_step_ids:
            return "empty_result_review"
        return "none"
    classified = {_classify_failure(f) for f in outcome.failed_steps}
    if "transient_retry" in classified:
        return "transient_retry"
    if "search_replan" in classified:
        return "search_replan"
    if "param_replan" in classified:
        return "param_replan"
    return "user_clarify"


def _classify_failure(failure: StepPushFailure) -> RecoveryKind:
    err = failure.error.casefold()
    if any(marker in err for marker in _TRANSIENT_MARKERS):
        return "transient_retry"
    if any(marker in err for marker in _SEARCH_INVALID_MARKERS):
        return "search_replan"
    if any(marker in err for marker in _VOCAB_MARKERS):
        return "param_replan"
    return "user_clarify"


def _derive_verification_section(state: PipelineState) -> VerificationSection:
    return VerificationSection(digest=state.verification_digest)
