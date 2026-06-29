from __future__ import annotations

from pathfinder.ai.graph.state import PipelineState
from pathfinder.ai.lead.intent import UserIntent
from pathfinder.ai.lead.ledger import (
    BuildSection,
    ConstraintSection,
    FrameSection,
    InvestigationLedger,
    RecoveryKind,
    VerificationSection,
)
from pathfinder.domain.strategy.build_outcome import (
    BuildOutcome,
    StepPushFailure,
)
from pathfinder.domain.strategy.constraints import (
    ground_constraints,
    merge_constraints,
    provisional_constraints,
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


def derive_ledger(
    state: PipelineState,
    intent: UserIntent | None,
) -> InvestigationLedger:
    """Pure derivation of the Ledger from PipelineState + the latest intent.

    No I/O. The Lead calls this on every turn. Sub-agents do NOT call it —
    they receive scoped slices via typed work orders from the Lead.
    """
    return InvestigationLedger(
        user_intent=intent,
        frame=FrameSection(spec=state.operational_spec),
        build=_derive_build_section(state),
        verification=_derive_verification_section(state),
        constraints=_derive_constraint_section(state, intent),
    )


def _derive_constraint_section(
    state: PipelineState, intent: UserIntent | None
) -> ConstraintSection:
    spec = state.operational_spec
    provisional = list(spec.constraints) if spec else []
    explicit = intent.explicit_constraints if intent else []
    merged = merge_constraints(provisional, explicit)
    if not merged:
        return ConstraintSection()
    if spec is None:
        return ConstraintSection(grounded=provisional_constraints(merged))
    search_names = [c.search_name for c in spec.criteria if c.search_name]
    param_names: set[str] = {p for c in spec.criteria for p in c.resolved_params}
    param_names |= {s.param_name for c in spec.criteria for s in c.open_params}
    param_names |= {s.param_name for s in spec.open_slots}
    return ConstraintSection(
        grounded=ground_constraints(
            merged, search_names=search_names, param_names=param_names
        )
    )


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
