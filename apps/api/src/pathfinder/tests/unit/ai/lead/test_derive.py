"""Ledger derivation: pure-function tests over sample PipelineState shapes."""

from __future__ import annotations

from uuid import uuid4

from pathfinder.ai.graph.state import (
    PhaseDisposition,
    PipelineState,
    StrategyDomainState,
    VerificationDigest,
)
from pathfinder.ai.lead.derive import derive_ledger
from pathfinder.ai.lead.intent import IntentClassification, UserIntent
from pathfinder.domain.strategy.build_outcome import (
    BuildOutcome,
    StepPushFailure,
)
from pathfinder.domain.strategy.operational_spec import (
    Criterion,
    OpenSlot,
    OperationalSpec,
    SpecStructure,
    StructureNode,
)


def _state(**domain: object) -> PipelineState:
    return PipelineState(
        conversation_id=uuid4(),
        user_id=uuid4(),
        site_id="plasmodb",
        mode="strategy",
        domain=StrategyDomainState.model_validate(domain),
    )


def _bound_spec() -> OperationalSpec:
    return OperationalSpec(
        goal="kinases",
        interpreted_goal="protein kinase genes",
        criteria=[
            Criterion(
                id="c1",
                text="protein kinases",
                search_name="GenesByGoTerm",
                resolved_params={},
            ),
        ],
        structure=SpecStructure(root=StructureNode(kind="leaf", criterion_id="c1")),
    )


def test_no_state_yields_empty_ledger() -> None:
    ledger = derive_ledger(_state(), None)
    assert ledger.frame.spec is None
    assert ledger.frame.present is False
    assert ledger.frame.criteria_count == 0
    assert ledger.build.outcome is None
    assert ledger.verification.digest is None


def test_frame_present_with_bound_spec_is_ready_to_build() -> None:
    ledger = derive_ledger(_state(operational_spec=_bound_spec()), None)
    assert ledger.frame.present is True
    assert ledger.frame.criteria_count == 1
    assert ledger.frame.bound_count == 1
    assert ledger.frame.open_slot_count == 0
    assert ledger.frame.needs_user is False
    assert ledger.frame.ready_to_build is True


def test_frame_open_param_slot_needs_user() -> None:
    spec = _bound_spec()
    spec.criteria[0].open_params = [
        OpenSlot(criterion_id="c1", param_name="dataset", question="Which dataset?"),
    ]
    ledger = derive_ledger(_state(operational_spec=spec), None)
    assert ledger.frame.open_slot_count == 1
    assert ledger.frame.needs_user is True
    assert ledger.frame.ready_to_build is False


def test_frame_unbound_criterion_is_not_ready() -> None:
    spec = OperationalSpec(
        goal="x",
        criteria=[Criterion(id="c1", text="x", search_name="")],
        structure=SpecStructure(root=StructureNode(kind="leaf", criterion_id="c1")),
    )
    ledger = derive_ledger(_state(operational_spec=spec), None)
    assert ledger.frame.criteria_count == 1
    assert ledger.frame.bound_count == 0
    assert ledger.frame.ready_to_build is False


def test_frame_render_section_surfaces_criteria_and_structure() -> None:
    ledger = derive_ledger(_state(operational_spec=_bound_spec()), None)
    rendered = ledger.render_section("frame")
    assert "GenesByGoTerm" in rendered
    assert "protein kinases" in rendered


def test_build_section_recovery_kind_empty_result() -> None:
    outcome = BuildOutcome(
        pushed_step_ids=["s1"],
        wdk_strategy_id=42,
        zero_step_ids=["s1"],
    )
    state = _state(last_build_outcome=outcome)
    ledger = derive_ledger(state, None)
    assert ledger.build.recovery_kind == "empty_result_review"
    assert ledger.build.needs_recovery is True
    assert ledger.build.succeeded is False


def test_build_section_recovery_kind_transient() -> None:
    outcome = BuildOutcome(
        failed_steps=[
            StepPushFailure(
                step_id="s1",
                search_name="X",
                error="WDK returned 503 — connection timed out",
            ),
        ],
    )
    state = _state(last_build_outcome=outcome)
    ledger = derive_ledger(state, None)
    assert ledger.build.recovery_kind == "transient_retry"


def test_build_section_recovery_kind_param_replan_on_vocab_error() -> None:
    outcome = BuildOutcome(
        failed_steps=[
            StepPushFailure(
                step_id="s1",
                search_name="X",
                error="Parameter validation failed: value not in vocab",
            ),
        ],
    )
    state = _state(last_build_outcome=outcome)
    ledger = derive_ledger(state, None)
    assert ledger.build.recovery_kind == "param_replan"


def test_build_section_succeeded() -> None:
    outcome = BuildOutcome(
        pushed_step_ids=["s1"],
        wdk_strategy_id=1,
        root_count=10,
    )
    state = _state(last_build_outcome=outcome)
    ledger = derive_ledger(state, None)
    assert ledger.build.succeeded is True
    assert ledger.build.recovery_kind == "none"


def test_verification_section_present() -> None:
    digest = VerificationDigest(
        disposition=PhaseDisposition.DONE,
        prose="all good",
        reason="ok",
        success=True,
    )
    state = _state(verification_digest=digest)
    ledger = derive_ledger(state, None)
    assert ledger.verification.complete is True
    assert ledger.verification.successful is True


def test_differential_intent_surfaces_in_summary() -> None:
    intent = UserIntent(
        raw_text="X vs Y",
        classification=IntentClassification.NEW_STRATEGY,
        inferred_goal="diff",
        is_differential=True,
        differential_sides=["gametocyte", "asexual blood stage"],
    )
    summary = derive_ledger(_state(), intent).render_summary()
    assert "differential" in summary
