"""Ledger derivation: pure-function tests over sample PipelineState shapes."""

from __future__ import annotations

from uuid import uuid4

from pydantic_ai.ui.vercel_ai.request_types import ToolApprovalResponded

from pathfinder.ai.agents.state import (
    ParamVocabSnapshot,
    SearchOverview,
)
from pathfinder.ai.graph.state import (
    ClarificationQuestion,
    PhaseDisposition,
    PipelineState,
    ProblemFrame,
    VerificationDigest,
)
from pathfinder.ai.lead.derive import derive_ledger
from pathfinder.ai.lead.intent import IntentClassification, UserIntent
from pathfinder.domain.parameters.wdk_vocab import VocabOption
from pathfinder.domain.strategy.build_outcome import (
    BuildOutcome,
    StepPushFailure,
)
from pathfinder.domain.strategy.plan import (
    ParamStatus,
    PlannedParameter,
    PlannedStep,
    PlanStatus,
    StepStatus,
    StepType,
    StrategyPlan,
    UserQuestion,
)


def _state(**kwargs: object) -> PipelineState:
    base: dict[str, object] = {
        "conversation_id": uuid4(),
        "user_id": uuid4(),
        "site_id": "plasmodb",
        "mode": "strategy",
    }
    base.update(kwargs)
    return PipelineState(**base)  # type: ignore[arg-type]


def _intent_diff(sides: tuple[str, str]) -> UserIntent:
    return UserIntent(
        raw_text="X vs Y",
        classification=IntentClassification.NEW_STRATEGY,
        inferred_goal="diff",
        is_differential=True,
        differential_sides=list(sides),
    )


def _gametocyte_only_search() -> SearchOverview:
    return SearchOverview(
        search_name="GenesByRNASeq_Bartfai",
        display_name="Bartfai gametocytes",
        record_type="transcript",
        description="gametocyte only",
        parameter_names=["sample"],
        required_params=["sample"],
        selection_status="selected",
        param_vocab={
            "sample": ParamVocabSnapshot(
                param_type="single-pick-vocabulary",
                required=True,
                help="Which RNA-seq sample to compare",
                allowed_values=[
                    VocabOption(value="male gametocyte", display="male gametocyte"),
                    VocabOption(value="female gametocyte", display="female gametocyte"),
                ],
            ),
        },
    )


def _full_lifecycle_search() -> SearchOverview:
    return SearchOverview(
        search_name="GenesByRNASeq_LopezBarragan",
        display_name="LopezBarragan full life-cycle",
        record_type="transcript",
        description="all stages",
        parameter_names=["sample"],
        required_params=["sample"],
        selection_status="selected",
        param_vocab={
            "sample": ParamVocabSnapshot(
                param_type="single-pick-vocabulary",
                required=True,
                allowed_values=[
                    VocabOption(value="gametocyte", display="gametocyte"),
                    VocabOption(
                        value="asexual blood stage",
                        display="asexual blood stage",
                    ),
                ],
            ),
        },
    )


def test_no_state_yields_empty_ledger() -> None:
    ledger = derive_ledger(_state(), None)
    assert ledger.frame.frame is None
    assert ledger.frame.needed is True
    assert ledger.discovery.selected_count == 0
    assert ledger.plan.plan is None
    assert ledger.build.outcome is None
    assert ledger.verification.digest is None


def test_frame_present_continuation_intent_matches() -> None:
    frame = ProblemFrame(user_goal="X", interpreted_goal="X")
    state = _state(problem_frame=frame)
    intent = UserIntent(
        raw_text="approve",
        classification=IntentClassification.APPROVAL,
        inferred_goal="approve",
    )
    ledger = derive_ledger(state, intent)
    assert ledger.frame.matches_current_intent is True
    assert ledger.frame.needed is False


def test_frame_present_new_strategy_does_not_match_unrelated_goal() -> None:
    frame = ProblemFrame(
        user_goal="kinase genes in P. falciparum gametocytes",
        interpreted_goal="kinase",
    )
    state = _state(problem_frame=frame)
    intent = UserIntent(
        raw_text="ascorbate biosynthesis pathway in T. cruzi",
        classification=IntentClassification.NEW_STRATEGY,
        inferred_goal="ascorbate biosynthesis pathway in T. cruzi",
    )
    ledger = derive_ledger(state, intent)
    assert ledger.frame.matches_current_intent is False
    assert ledger.frame.needed is True


def test_blocking_questions_carried_through() -> None:
    frame = ProblemFrame(
        user_goal="X",
        interpreted_goal="X",
        blocking_questions=[ClarificationQuestion(question="which strain?")],
    )
    state = _state(problem_frame=frame)
    intent = UserIntent(
        raw_text="hi",
        classification=IntentClassification.APPROVAL,
        inferred_goal="x",
    )
    ledger = derive_ledger(state, intent)
    assert len(ledger.frame.blocking_questions_unanswered) == 1
    assert ledger.frame.blocked is True


def test_intent_satisfied_false_when_only_gametocyte_search() -> None:
    state = _state(
        discovered_searches={"GenesByRNASeq_Bartfai": _gametocyte_only_search()},
    )
    intent = _intent_diff(("gametocyte", "asexual blood stage"))
    ledger = derive_ledger(state, intent)
    assert ledger.discovery.selected_count == 1
    assert ledger.discovery.intent_satisfied is False
    assert ledger.discovery.intent_gap is not None
    assert "asexual" in ledger.discovery.intent_gap
    assert ledger.discovery.needs_more_discovery is True


def test_intent_satisfied_true_when_full_lifecycle_search_added() -> None:
    state = _state(
        discovered_searches={
            "GenesByRNASeq_Bartfai": _gametocyte_only_search(),
            "GenesByRNASeq_LopezBarragan": _full_lifecycle_search(),
        },
    )
    intent = _intent_diff(("gametocyte", "asexual blood stage"))
    ledger = derive_ledger(state, intent)
    assert ledger.discovery.intent_satisfied is True
    assert ledger.discovery.intent_gap is None
    assert ledger.discovery.needs_more_discovery is False


def test_intent_non_differential_satisfied_when_any_selected() -> None:
    state = _state(
        discovered_searches={"GenesByRNASeq_Bartfai": _gametocyte_only_search()},
    )
    intent = UserIntent(
        raw_text="kinase genes",
        classification=IntentClassification.NEW_STRATEGY,
        inferred_goal="kinase",
    )
    ledger = derive_ledger(state, intent)
    assert ledger.discovery.intent_satisfied is True


def test_discovery_section_render_surfaces_param_help_and_vocab() -> None:
    """read_ledger_section('discovery') exposes each search's params with
    help text ('what it does') and enumerated vocab — the observability the
    Lead needs to catch param mistakes before planning."""
    state = _state(
        discovered_searches={"GenesByRNASeq_Bartfai": _gametocyte_only_search()},
    )
    ledger = derive_ledger(state, _intent_diff(("gametocyte", "asexual blood stage")))
    rendered = ledger.render_section("discovery")
    assert "sample" in rendered
    assert "Which RNA-seq sample to compare" in rendered
    assert "male gametocyte" in rendered


def _plan_with_user_slot() -> StrategyPlan:
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
                        name="hard_floor",
                        display_name="Hard Floor",
                        param_type="single-pick-vocabulary",
                        value=None,
                        status=ParamStatus.NEEDS_USER_INPUT,
                        required=True,
                    ),
                ],
            ),
        ],
        connections=[],
        questions=[
            UserQuestion(
                id="q1",
                question="Pick a tier",
                related_step="s1",
                related_param="hard_floor",
            ),
        ],
    )


def test_plan_open_user_input_slots() -> None:
    state = _state(active_plan=_plan_with_user_slot())
    ledger = derive_ledger(state, None)
    assert len(ledger.plan.open_user_input_slots) == 1
    slot = ledger.plan.open_user_input_slots[0]
    assert slot.step_id == "s1"
    assert slot.param_name == "hard_floor"
    assert slot.question == "Pick a tier"
    assert ledger.plan.blocked_kind == "needs_user"
    assert ledger.plan.ready_to_execute is False


def test_plan_approved_and_clean_is_ready_to_execute() -> None:
    plan = _plan_with_user_slot()
    plan.steps[0].parameters[0].value = "tier_3"
    plan.steps[0].parameters[0].status = ParamStatus.USER_SET
    plan.status = PlanStatus.APPROVED
    state = _state(active_plan=plan)
    ledger = derive_ledger(state, None)
    assert ledger.plan.ready_to_execute is True
    assert ledger.plan.blocked_kind == "none"


def test_plan_denial_surfaces_reason_when_unapproved() -> None:
    plan = _plan_with_user_slot()
    state = _state(
        active_plan=plan,
        approval_responses={
            "call_1": ToolApprovalResponded(
                id="call_1",
                approved=False,
                reason="Use GO molecular function for kinases, not the InterPro PFAM domain.",
            ),
        },
    )
    ledger = derive_ledger(state, None)
    assert ledger.plan.last_denial_message == (
        "Use GO molecular function for kinases, not the InterPro PFAM domain."
    )


def test_plan_denial_not_surfaced_once_approved() -> None:
    plan = _plan_with_user_slot()
    plan.status = PlanStatus.APPROVED
    state = _state(
        active_plan=plan,
        approval_responses={
            "call_1": ToolApprovalResponded(
                id="call_1", approved=False, reason="old denial"
            ),
            "call_2": ToolApprovalResponded(id="call_2", approved=True, reason=""),
        },
    )
    ledger = derive_ledger(state, None)
    assert ledger.plan.last_denial_message is None


def test_plan_denial_takes_most_recent_denied_response() -> None:
    plan = _plan_with_user_slot()
    state = _state(
        active_plan=plan,
        approval_responses={
            "call_1": ToolApprovalResponded(
                id="call_1", approved=False, reason="first"
            ),
            "call_2": ToolApprovalResponded(
                id="call_2", approved=False, reason="second"
            ),
        },
    )
    ledger = derive_ledger(state, None)
    assert ledger.plan.last_denial_message == "second"


def test_render_summary_surfaces_denial_message() -> None:
    plan = _plan_with_user_slot()
    state = _state(
        active_plan=plan,
        approval_responses={
            "call_1": ToolApprovalResponded(
                id="call_1", approved=False, reason="Use GO, not InterPro."
            ),
        },
    )
    summary = derive_ledger(state, None).render_summary()
    assert "Use GO, not InterPro." in summary


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
