"""Checkpoint payloads must survive STRICT msgpack deserialization.

LangGraph currently warns ("Deserializing unregistered type ... will be
blocked in a future version") and still decodes. When it flips to strict,
any type not on the allowlist fails to deserialize — which would make every
persisted conversation unresumable. These tests pin the allowlist by
round-tripping each type through a STRICT serializer, so a new state type
that nobody registered fails here instead of after a LangGraph upgrade.
"""

from datetime import UTC, datetime
from uuid import UUID

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from pydantic_ai.ui.vercel_ai.request_types import TextUIPart

from pathfinder.ai.agents.state import SearchOverview
from pathfinder.ai.conversation.serde import (
    CHECKPOINT_MSGPACK_TYPES,
    build_checkpoint_serde,
)
from pathfinder.ai.graph.state import (
    PendingApproval,
    PhaseDisposition,
    SubAgentApprovalCall,
    SubAgentApprovalPending,
    VerificationDigest,
)
from pathfinder.ai.lead.intent import IntentClassification, UserIntent
from pathfinder.ai.memory.schemas import MemoryValue
from pathfinder.domain.strategy.build_outcome import BuildOutcome, NodeResult
from pathfinder.domain.strategy.constraints import ConstraintKind, ConstraintSource
from pathfinder.domain.strategy.operational_spec import OperationalSpec


def _overview(record_type: str) -> SearchOverview:
    return SearchOverview(
        search_name="GenesByTaxon",
        display_name="Genes by Taxon",
        record_type=record_type,
        description="Organism-scoped gene search",
        parameter_names=["organism"],
        required_params=["organism"],
    )


def _strict_roundtrip(value: object) -> object:
    """Encode with our serde, decode under a STRICT (no-fallback) serializer."""
    serde = build_checkpoint_serde()
    type_, payload = serde.dumps_typed(value)
    strict = JsonPlusSerializer(allowed_msgpack_modules=None).with_msgpack_allowlist(
        CHECKPOINT_MSGPACK_TYPES
    )
    return strict.loads_typed((type_, payload))


def test_every_registered_type_is_a_real_class() -> None:
    # Guards against a typo'd/renamed entry silently dropping off the allowlist.
    assert CHECKPOINT_MSGPACK_TYPES
    for entry in CHECKPOINT_MSGPACK_TYPES:
        assert isinstance(entry, type), entry


def test_search_overview_survives_strict_roundtrip() -> None:
    value = _overview("transcript")
    assert _strict_roundtrip(value) == value


def test_memory_value_survives_strict_roundtrip() -> None:
    value = MemoryValue(
        kind="knowledge",
        name="obp-note",
        summary="OBPs are odorant binding proteins",
        content={"detail": "vectorbase"},
        created_at=datetime(2026, 8, 7, tzinfo=UTC),
    )
    assert _strict_roundtrip(value) == value


def test_constraint_enums_survive_strict_roundtrip() -> None:
    assert _strict_roundtrip(ConstraintKind.ORGANISM) == ConstraintKind.ORGANISM
    assert (
        _strict_roundtrip(ConstraintSource.USER_EXPLICIT)
        == ConstraintSource.USER_EXPLICIT
    )


def test_vercel_text_part_survives_strict_roundtrip() -> None:
    # pydantic-ai's own type also lands in checkpoints via the message history.
    value = TextUIPart(text="hello")
    assert _strict_roundtrip(value) == value


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


def test_pending_sub_agent_approval_survives_strict_roundtrip() -> None:
    # A sub-agent approval checkpoints the run that must be re-entered, so the
    # nested models ride into the checkpoint with the approval.
    value = PendingApproval(
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
    assert _strict_roundtrip(value) == value


def test_all_observed_checkpoint_types_are_registered() -> None:
    # The exact set observed deserializing unregistered in worker logs.
    observed = {
        SearchOverview,
        PhaseDisposition,
        VerificationDigest,
        IntentClassification,
        UserIntent,
        MemoryValue,
        BuildOutcome,
        NodeResult,
        ConstraintKind,
        ConstraintSource,
        OperationalSpec,
        TextUIPart,
    }
    missing = observed - set(CHECKPOINT_MSGPACK_TYPES)
    assert missing == set(), f"unregistered checkpoint types: {missing}"
