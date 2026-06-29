"""Lead module type-shape sanity tests.

These lock the surface so derivation, lead agent, and sub-agent wrappers can
rely on stable contracts. Each test asserts a specific field/computed value.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from pathfinder.ai.graph.state import PhaseDisposition, VerificationDigest
from pathfinder.ai.lead.deltas import (
    ExecuteDelta,
    FrameResult,
    RecoveryDelta,
    VerificationDelta,
)
from pathfinder.ai.lead.intent import IntentClassification, UserIntent
from pathfinder.ai.lead.ledger import (
    BuildSection,
    FrameSection,
    InvestigationLedger,
    SubAgentCallRecord,
    VerificationSection,
)
from pathfinder.domain.strategy.build_outcome import BuildOutcome
from pathfinder.domain.strategy.operational_spec import (
    Criterion,
    OpenSlot,
    OperationalSpec,
    SpecStructure,
    StructureNode,
)


def test_user_intent_default_non_differential() -> None:
    intent = UserIntent(
        raw_text="hello",
        classification=IntentClassification.OFF_TOPIC,
        inferred_goal="say hi",
    )
    assert intent.is_differential is False
    assert intent.differential_sides == []
    assert intent.referenced_step_ids == []


def test_user_intent_differential_sides_two_items() -> None:
    intent = UserIntent(
        raw_text="X vs Y",
        classification=IntentClassification.NEW_STRATEGY,
        inferred_goal="diff",
        is_differential=True,
        differential_sides=["X", "Y"],
    )
    assert intent.differential_sides == ["X", "Y"]


def test_user_intent_differential_sides_rejects_three() -> None:
    with pytest.raises(ValidationError):
        UserIntent(
            raw_text="X vs Y vs Z",
            classification=IntentClassification.NEW_STRATEGY,
            inferred_goal="diff",
            is_differential=True,
            differential_sides=["X", "Y", "Z"],
        )


def test_frame_result_disposition_default_spec_ready() -> None:
    result = FrameResult(summary="bound 3 criteria")
    assert result.disposition == "spec_ready"
    assert result.open_questions == []


def test_frame_result_needs_user_carries_questions() -> None:
    result = FrameResult(
        summary="one open slot",
        disposition="needs_user",
        open_questions=["Which RNA-seq dataset?"],
    )
    assert result.disposition == "needs_user"
    assert result.open_questions == ["Which RNA-seq dataset?"]


def test_execute_delta_carries_outcome() -> None:
    outcome = BuildOutcome(pushed_step_ids=["s1"], wdk_strategy_id=42, root_count=152)
    delta = ExecuteDelta(outcome=outcome)
    assert delta.outcome.root_count == 152


def test_recovery_delta_is_light() -> None:
    delta = RecoveryDelta(actions_taken=["rebuilt s1"], follow_up_needed=False)
    assert delta.actions_taken == ["rebuilt s1"]
    assert not hasattr(delta, "final_outcome")


def test_verification_delta_carries_digest() -> None:
    digest = VerificationDigest(
        disposition=PhaseDisposition.DONE,
        prose="all good",
        reason="checks pass",
        success=True,
    )
    delta = VerificationDelta(digest=digest)
    assert delta.digest.success is True


def _ready_spec() -> OperationalSpec:
    return OperationalSpec(
        goal="g",
        criteria=[Criterion(id="c1", text="x", search_name="GenesByTaxon")],
        structure=SpecStructure(root=StructureNode(kind="leaf", criterion_id="c1")),
    )


def test_frame_section_absent_when_no_spec() -> None:
    section = FrameSection(spec=None)
    assert section.present is False
    assert section.needs_user is False
    assert section.ready_to_build is False


def test_frame_section_needs_user_with_open_slot() -> None:
    spec = _ready_spec()
    spec.criteria[0].open_params = [OpenSlot(criterion_id="c1", param_name="dataset")]
    section = FrameSection(spec=spec)
    assert section.present is True
    assert section.open_slot_count == 1
    assert section.needs_user is True
    assert section.ready_to_build is False


def test_frame_section_ready_to_build_when_bound() -> None:
    section = FrameSection(spec=_ready_spec())
    assert section.bound_count == 1
    assert section.ready_to_build is True


def test_build_section_succeeded() -> None:
    outcome = BuildOutcome(pushed_step_ids=["s1"], wdk_strategy_id=1, root_count=10)
    section = BuildSection(outcome=outcome, pushed_count=1)
    assert section.succeeded is True


def test_build_section_not_succeeded_with_failures() -> None:
    section = BuildSection(failed_count=1)
    assert section.succeeded is False


def test_verification_section_successful_only_when_digest_success() -> None:
    digest_ok = VerificationDigest(
        disposition=PhaseDisposition.DONE,
        prose="ok",
        reason="x",
        success=True,
    )
    section_ok = VerificationSection(digest=digest_ok)
    assert section_ok.successful is True
    section_pending = VerificationSection()
    assert section_pending.successful is False


def test_investigation_ledger_compose() -> None:
    ledger = InvestigationLedger(
        user_intent=None,
        frame=FrameSection(spec=None),
        build=BuildSection(),
        verification=VerificationSection(),
    )
    assert ledger.frame.present is False
    assert ledger.build.succeeded is False
    assert ledger.sub_agent_calls_total == 0


def test_sub_agent_call_record_shape() -> None:
    rec = SubAgentCallRecord(
        sub_agent="frame",
        called_at_turn="t1",
        input_summary="frame the goal",
        output_summary="3 criteria",
        succeeded=True,
    )
    assert rec.sub_agent == "frame"
