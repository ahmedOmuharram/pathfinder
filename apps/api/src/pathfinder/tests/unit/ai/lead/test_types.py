"""Lead module type-shape sanity tests.

These lock the surface so later tasks (derivation, lead agent, sub-agent
wrappers) can rely on stable contracts. Each test asserts a specific
field/computed value — not "imports work" but "the type does what its
docstring says."
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from pathfinder.ai.graph.state import PhaseDisposition, VerificationDigest
from pathfinder.ai.lead.deltas import (
    DiscoveryDelta,
    ExecuteDelta,
    OpenSlot,
    PlanDelta,
    VerificationDelta,
)
from pathfinder.ai.lead.intent import IntentClassification, UserIntent
from pathfinder.ai.lead.ledger import (
    BuildSection,
    DiscoverySection,
    FrameSection,
    InvestigationLedger,
    PlanSection,
    SubAgentCallRecord,
    VerificationSection,
)
from pathfinder.domain.parameters.values import StringValue
from pathfinder.domain.strategy.build_outcome import BuildOutcome
from pathfinder.domain.strategy.plan import (
    ParamStatus,
    PlannedParameter,
    PlannedStep,
    PlanStatus,
    StepStatus,
    StepType,
    StrategyPlan,
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


def test_open_slot_status_literal() -> None:
    slot = OpenSlot(
        step_id="s1",
        param_name="hard_floor",
        status="needs_user_input",
        question="Pick a tier",
    )
    assert slot.status == "needs_user_input"


def _plan_with_unresolved_slot() -> StrategyPlan:
    return StrategyPlan(
        title="t",
        description="d",
        rationale="r",
        steps=[
            PlannedStep(
                id="s1",
                search_name="X",
                display_name="X",
                step_type=StepType.LEAF,
                status=StepStatus.READY,
                parameters=[
                    PlannedParameter(
                        name="p",
                        display_name="p",
                        param_type="string",
                        value=None,
                        status=ParamStatus.NEEDS_USER_INPUT,
                        required=True,
                    ),
                ],
            ),
        ],
        connections=[],
    )


def _plan_all_set() -> StrategyPlan:
    return StrategyPlan(
        title="t",
        description="d",
        rationale="r",
        status=PlanStatus.APPROVED,
        steps=[
            PlannedStep(
                id="s1",
                search_name="X",
                display_name="X",
                step_type=StepType.LEAF,
                status=StepStatus.READY,
                parameters=[
                    PlannedParameter(
                        name="p",
                        display_name="p",
                        param_type="string",
                        value=StringValue(value="v"),
                        status=ParamStatus.SET,
                        required=True,
                    ),
                ],
            ),
        ],
        connections=[],
    )


def test_plan_delta_has_unresolved_slots_true() -> None:
    delta = PlanDelta(plan=_plan_with_unresolved_slot())
    assert delta.has_unresolved_slots is True


def test_plan_delta_has_unresolved_slots_false() -> None:
    delta = PlanDelta(plan=_plan_all_set())
    assert delta.has_unresolved_slots is False


def test_execute_delta_carries_outcome() -> None:
    outcome = BuildOutcome(pushed_step_ids=["s1"], wdk_strategy_id=42, root_count=152)
    delta = ExecuteDelta(outcome=outcome)
    assert delta.outcome.root_count == 152


def test_discovery_delta_defaults_empty() -> None:
    delta = DiscoveryDelta(findings_summary="found nothing")
    assert delta.new_selections == []
    assert delta.new_rejections == []


def test_verification_delta_carries_digest() -> None:
    digest = VerificationDigest(
        disposition=PhaseDisposition.DONE,
        prose="all good",
        reason="checks pass",
        success=True,
    )
    delta = VerificationDelta(digest=digest)
    assert delta.digest.success is True


def test_frame_section_needed_when_no_frame() -> None:
    section = FrameSection(frame=None, matches_current_intent=False)
    assert section.needed is True
    assert section.blocked is False


def test_plan_section_blocked_kind_needs_user_when_user_slots_open() -> None:
    section = PlanSection(
        plan=_plan_with_unresolved_slot(),
        open_user_input_slots=[
            OpenSlot(
                step_id="s1",
                param_name="p",
                status="needs_user_input",
                question="?",
            ),
        ],
    )
    assert section.blocked_kind == "needs_user"
    assert section.ready_to_execute is False


def test_plan_section_ready_to_execute_when_approved_and_clean() -> None:
    section = PlanSection(plan=_plan_all_set(), approved=True)
    assert section.blocked_kind == "none"
    assert section.ready_to_execute is True


def test_build_section_succeeded() -> None:
    outcome = BuildOutcome(pushed_step_ids=["s1"], wdk_strategy_id=1, root_count=10)
    section = BuildSection(outcome=outcome, pushed_count=1)
    assert section.succeeded is True


def test_build_section_not_succeeded_with_failures() -> None:
    section = BuildSection(failed_count=1)
    assert section.succeeded is False


def test_discovery_section_needs_more_discovery_when_zero_selections() -> None:
    section = DiscoverySection(selected_count=0, intent_satisfied=False)
    assert section.needs_more_discovery is True


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
        frame=FrameSection(frame=None, matches_current_intent=False),
        discovery=DiscoverySection(),
        plan=PlanSection(),
        build=BuildSection(),
        verification=VerificationSection(),
    )
    assert ledger.frame.needed is True
    assert ledger.plan.blocked_kind == "none"
    assert ledger.sub_agent_calls_total == 0


def test_sub_agent_call_record_shape() -> None:
    rec = SubAgentCallRecord(
        sub_agent="discover",
        called_at_turn="t1",
        input_summary="find searches",
        output_summary="2 selections",
        succeeded=True,
    )
    assert rec.sub_agent == "discover"
