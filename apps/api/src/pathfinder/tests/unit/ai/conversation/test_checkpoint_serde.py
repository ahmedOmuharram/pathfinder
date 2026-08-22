"""Checkpoint payloads must survive STRICT msgpack deserialization.

LangGraph currently warns ("Deserializing unregistered type ... will be
blocked in a future version") and still decodes. When it flips to strict,
any type not on the allowlist fails to deserialize — which would make every
persisted conversation unresumable. These tests pin the allowlist by
round-tripping each type through a STRICT serializer, so a new state type
that nobody registered fails here instead of after a LangGraph upgrade.
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from pydantic_ai.ui.vercel_ai.request_types import TextUIPart, ToolApprovalResponded

from pathfinder.ai.agents.state import SearchOverview
from pathfinder.ai.graph.state import (
    PhaseDisposition,
    PipelineState,
    StrategyDomainState,
    VerificationDigest,
)
from pathfinder.ai.lead.intent import IntentClassification, UserIntent
from pathfinder.assistant_core.conversation.serde import (
    CORE_CHECKPOINT_TYPES,
    build_checkpoint_serde,
    checkpoint_types,
)
from pathfinder.assistant_core.graph.turn_state import (
    PendingApproval,
    SubAgentApprovalCall,
    SubAgentApprovalPending,
    UserQuestionAnswer,
)
from pathfinder.assistant_core.memory.schemas import MemoryValue
from pathfinder.domain.strategy.build_outcome import (
    BuildOutcome,
    NodeResult,
    StepPushFailure,
)
from pathfinder.domain.strategy.constraints import ConstraintKind, ConstraintSource
from pathfinder.domain.strategy.operational_spec import Criterion, OperationalSpec
from pathfinder.domain.strategy.staleness import StaleBuild


def _overview(record_type: str) -> SearchOverview:
    return SearchOverview(
        search_name="GenesByTaxon",
        display_name="Genes by Taxon",
        record_type=record_type,
        description="Organism-scoped gene search",
        parameter_names=["organism"],
        required_params=["organism"],
    )


def _memory() -> MemoryValue:
    return MemoryValue(
        kind="knowledge",
        name="obp-note",
        summary="OBPs are odorant binding proteins",
        content={"detail": "vectorbase"},
        created_at=datetime(2026, 8, 7, tzinfo=UTC),
    )


def _pending_approval() -> PendingApproval:
    return PendingApproval(
        phase="verification",
        tool_call_id="call_verify_strategy",
        tool_name="verify_strategy",
        tool_args={"reason": "optimize the fold change"},
        prior_messages_json='[{"kind":"request","parts":[]}]',
        user_message_id=UUID("01a011a9-5c65-74b2-8813-215ab5b382fa"),
        sub_agent=SubAgentApprovalPending(
            role="verification",
            approvals=[
                SubAgentApprovalCall(
                    tool_call_id="call_optimize_search_parameters",
                    tool_name="optimize_search_parameters",
                    args={"settings": {"budget": 8}},
                ),
            ],
            messages_json='[{"kind":"response","parts":[]}]',
        ),
    )


def _digest() -> VerificationDigest:
    return VerificationDigest(
        disposition=PhaseDisposition.DONE,
        prose="Strategy ready.",
        reason="verification successful",
        success=True,
        key_findings=["1234 hits"],
    )


def _outcome() -> BuildOutcome:
    return BuildOutcome(
        pushed_step_ids=["s1"],
        failed_steps=[
            StepPushFailure(step_id="s2", search_name="GenesByGoTerm", error="500"),
        ],
        wdk_strategy_id=330423363,
        root_count=132,
        node_results=[
            NodeResult(
                node_id="s1",
                search_name="GenesByTaxon",
                wdk_step_id=1,
                count=132,
                status="ok",
            ),
        ],
    )


def _spec() -> OperationalSpec:
    return OperationalSpec(
        goal="find drug targets",
        interpreted_goal="protein kinases in P. falciparum",
        criteria=[Criterion(id="c1", text="kinases", search_name="GenesByGoTerm")],
    )


def _intent() -> UserIntent:
    return UserIntent(
        raw_text="find drug targets",
        classification=IntentClassification.NEW_STRATEGY,
        inferred_goal="protein kinases",
    )


def _domain() -> StrategyDomainState:
    return StrategyDomainState(
        user_intent=_intent(),
        lead_next_state="complete",
        operational_spec=_spec(),
        discovered_searches={"GenesByTaxon": _overview("transcript")},
        verification_digest=_digest(),
        last_build_outcome=_outcome(),
        stale_build=StaleBuild(added_nodes=["s3"], removed_nodes=["s0"]),
        created_gene_set_ids=["gs-1"],
    )


def _populated_state() -> PipelineState:
    return PipelineState(
        conversation_id=uuid4(),
        user_id=uuid4(),
        site_id="plasmodb",
        mode="strategy",
        user_message_id=uuid4(),
        user_prompt="find drug targets",
        user_parts=[TextUIPart(text="find drug targets", state="done")],
        turn_trace_id=str(uuid4()),
        turn_created_at="2026-08-21T00:00:00+00:00",
        turn_start_event_id=7,
        turn_total_tokens=1234,
        turn_total_cost_usd=Decimal("0.0042"),
        pending_approval=_pending_approval(),
        approval_responses={
            "call_verify_strategy": ToolApprovalResponded(
                id="call_verify_strategy",
                approved=True,
            ),
        },
        user_question_answers={
            "call_consult": [
                UserQuestionAnswer(
                    question_id="q1",
                    prompt="Fold-change threshold?",
                    chosen_labels=["2-fold"],
                ),
            ],
        },
        retrieved_memories=[_memory()],
        domain=_domain(),
    )


SAMPLES: dict[type, object] = {
    TextUIPart: TextUIPart(text="hello"),
    ToolApprovalResponded: ToolApprovalResponded(id="call_1", approved=True),
    MemoryValue: _memory(),
    PendingApproval: _pending_approval(),
    SubAgentApprovalPending: _pending_approval().sub_agent,
    SubAgentApprovalCall: SubAgentApprovalCall(
        tool_call_id="call_delete_step",
        tool_name="delete_step",
        args={"step_id": "s2"},
    ),
    UserQuestionAnswer: UserQuestionAnswer(
        question_id="q1",
        prompt="Fold-change threshold?",
        chosen_labels=["2-fold"],
    ),
    SearchOverview: _overview("transcript"),
    PhaseDisposition: PhaseDisposition.DONE,
    VerificationDigest: _digest(),
    IntentClassification: IntentClassification.NEW_STRATEGY,
    UserIntent: _intent(),
    BuildOutcome: _outcome(),
    NodeResult: _outcome().node_results[0],
    StepPushFailure: _outcome().failed_steps[0],
    ConstraintKind: ConstraintKind.ORGANISM,
    ConstraintSource: ConstraintSource.USER_EXPLICIT,
    OperationalSpec: _spec(),
    StaleBuild: StaleBuild(added_nodes=["s3"]),
    StrategyDomainState: _domain(),
}


def _strict_roundtrip(value: object) -> object:
    """Encode with our serde, decode under a STRICT (no-fallback) serializer."""
    serde = build_checkpoint_serde()
    type_, payload = serde.dumps_typed(value)
    strict = JsonPlusSerializer(allowed_msgpack_modules=None).with_msgpack_allowlist(
        checkpoint_types()
    )
    return strict.loads_typed((type_, payload))


def test_every_registered_type_is_a_real_class() -> None:
    # Guards against a typo'd/renamed entry silently dropping off the allowlist.
    assert checkpoint_types()
    for entry in checkpoint_types():
        assert isinstance(entry, type), entry


def test_the_core_allowlist_holds_no_strategy_type() -> None:
    """A second assistant inherits the core tuple, so science must not be in it."""
    assert set(CORE_CHECKPOINT_TYPES).isdisjoint(
        {
            SearchOverview,
            VerificationDigest,
            OperationalSpec,
            BuildOutcome,
            StrategyDomainState,
        },
    )


def test_importing_the_product_state_registers_its_types() -> None:
    """The registration rides on the module the graph already imports."""
    registered = set(checkpoint_types()) - set(CORE_CHECKPOINT_TYPES)
    assert registered == {
        SearchOverview,
        PhaseDisposition,
        VerificationDigest,
        IntentClassification,
        UserIntent,
        BuildOutcome,
        NodeResult,
        StepPushFailure,
        ConstraintKind,
        ConstraintSource,
        OperationalSpec,
        StaleBuild,
        StrategyDomainState,
    }


def test_every_allowlisted_type_has_a_sample() -> None:
    assert set(checkpoint_types()) == set(SAMPLES)


def test_every_allowlisted_type_survives_strict_roundtrip() -> None:
    for type_, sample in SAMPLES.items():
        assert _strict_roundtrip(sample) == sample, type_


def test_a_populated_state_survives_strict_roundtrip_channel_by_channel() -> None:
    """LangGraph gives every top-level field its own channel, so each field
    value is encoded on its own."""
    state = _populated_state()
    for name in PipelineState.model_fields:
        value = getattr(state, name)
        assert _strict_roundtrip(value) == value, name


def test_a_populated_state_rebuilds_from_its_round_tripped_channels() -> None:
    state = _populated_state()
    channels = {
        name: _strict_roundtrip(getattr(state, name))
        for name in PipelineState.model_fields
    }
    assert PipelineState.model_validate(channels) == state


def test_a_populated_state_keeps_its_nested_types() -> None:
    restored = _strict_roundtrip(_populated_state().domain)
    assert isinstance(restored, StrategyDomainState)
    outcome = restored.last_build_outcome
    assert outcome is not None
    assert isinstance(outcome.failed_steps[0], StepPushFailure)
    assert isinstance(outcome.node_results[0], NodeResult)
    assert isinstance(restored.discovered_searches["GenesByTaxon"], SearchOverview)


def test_nested_state_container_survives_strict_roundtrip() -> None:
    # The realistic shape: mixed pathfinder types nested inside plain containers.
    value = {
        "overviews": [_overview("gene")],
        "kinds": [ConstraintKind.ORGANISM],
    }
    assert _strict_roundtrip(value) == value


def test_tuples_restore_as_lists() -> None:
    # msgpack has no tuple type. Pinned so state that round-trips through a
    # checkpoint is never compared against a tuple and silently mismatched.
    assert _strict_roundtrip((ConstraintKind.ORGANISM,)) == [ConstraintKind.ORGANISM]
