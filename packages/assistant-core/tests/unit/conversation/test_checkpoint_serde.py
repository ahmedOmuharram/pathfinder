"""A checkpoint must survive a STRICT msgpack decode with nothing else installed.

LangGraph decodes an unregistered type today and warns; when it stops, a type
missing from the allowlist makes every persisted thread unresumable. Each type
here is encoded by the runtime's serializer and decoded by a strict one, so an
unregistered type fails in this suite rather than after an upgrade.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from pydantic import BaseModel
from pydantic_ai.ui.vercel_ai.request_types import TextUIPart, ToolApprovalResponded
from tests.synthetic import (
    SYNTHETIC_MODE,
    SYNTHETIC_SITE_ID,
    UsageLedger,
    synthetic_spec,
)

from assistant_core.conversation.serde import (
    CORE_CHECKPOINT_TYPES,
    build_checkpoint_serde,
    checkpoint_types,
)
from assistant_core.graph.turn_state import (
    PendingApproval,
    SubAgentApprovalCall,
    SubAgentApprovalPending,
    TurnState,
    UserQuestionAnswer,
)
from assistant_core.memory.schemas import MemoryValue


class UnregisteredState(BaseModel):
    """A state type no spec declared."""

    note: str


def _turn_state() -> TurnState:
    return TurnState(
        conversation_id=UUID("01a011a9-5c65-74b2-8813-215ab5b382fa"),
        user_id=uuid4(),
        site_id=SYNTHETIC_SITE_ID,
        mode=SYNTHETIC_MODE,
        user_prompt="which sites",
        user_parts=[TextUIPart(text="which sites", state="done")],
        turn_total_tokens=51,
        turn_total_cost_usd=Decimal("0.0125"),
        approval_responses={"call_wipe": ToolApprovalResponded(id="a1", approved=True)},
        user_question_answers={
            "call_ask": [UserQuestionAnswer(question_id="q1", prompt="which?")],
        },
        retrieved_memories=[_memory()],
    )


def _memory() -> MemoryValue:
    return MemoryValue(
        kind="knowledge",
        name="a-note",
        summary="one remembered fact",
        content={"detail": "value"},
        created_at=datetime(2026, 8, 22, tzinfo=UTC),
    )


_SAMPLES: dict[type, object] = {
    TextUIPart: TextUIPart(text="hello", state="done"),
    ToolApprovalResponded: ToolApprovalResponded(id="a1", approved=False),
    MemoryValue: _memory(),
    PendingApproval: PendingApproval(
        phase="answer",
        tool_call_id="call_wipe",
        tool_name="wipe_everything",
        tool_args={"target": "everything"},
        prior_messages_json='[{"kind":"request","parts":[]}]',
        sub_agent=SubAgentApprovalPending(
            role="answer",
            approvals=[SubAgentApprovalCall(tool_call_id="call_wipe", tool_name="w")],
        ),
    ),
    SubAgentApprovalPending: SubAgentApprovalPending(role="answer"),
    SubAgentApprovalCall: SubAgentApprovalCall(
        tool_call_id="call_wipe",
        tool_name="wipe_everything",
    ),
    UserQuestionAnswer: UserQuestionAnswer(question_id="q1", prompt="which?"),
}


def _strict_roundtrip(value: object, *, declared: tuple[type, ...] = ()) -> object:
    strict = JsonPlusSerializer(allowed_msgpack_modules=None).with_msgpack_allowlist(
        checkpoint_types(declared),
    )
    return strict.loads_typed(build_checkpoint_serde(declared).dumps_typed(value))


def test_every_core_type_has_a_sample_in_this_suite() -> None:
    assert set(CORE_CHECKPOINT_TYPES) == set(_SAMPLES)


@pytest.mark.parametrize("core_type", CORE_CHECKPOINT_TYPES, ids=lambda t: t.__name__)
def test_a_core_type_survives_a_strict_round_trip(core_type: type) -> None:
    sample = _SAMPLES[core_type]

    assert _strict_roundtrip(sample) == sample


def test_the_state_type_a_spec_declares_survives_a_strict_round_trip() -> None:
    spec = synthetic_spec(UsageLedger())
    state = _turn_state()

    restored = _strict_roundtrip(state, declared=spec.checkpoint_types)

    assert restored == state


def test_a_state_type_no_spec_declares_does_not_survive() -> None:
    restored = _strict_roundtrip(UnregisteredState(note="undeclared"))

    assert not isinstance(restored, UnregisteredState)
