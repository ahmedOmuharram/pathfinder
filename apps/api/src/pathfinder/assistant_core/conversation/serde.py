"""Checkpoint serializer with an explicit msgpack type allowlist.

LangGraph decodes unregistered types with a deprecation warning today and
will refuse them in a future release. Every type that reaches a checkpoint
must therefore be on the allowlist, or upgrading LangGraph would make
existing conversations unresumable.

Core types are listed here. A product declares its own state types with
:func:`register_checkpoint_types` at import time; the strict round-trip
tests in ``tests/unit/ai/conversation/test_checkpoint_serde.py`` fail on
any allowlisted type that does not survive a strict decode.
"""

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from pydantic_ai.ui.vercel_ai.request_types import (
    TextUIPart,
    ToolApprovalResponded,
)

from pathfinder.assistant_core.graph.turn_state import (
    PendingApproval,
    SubAgentApprovalCall,
    SubAgentApprovalPending,
    UserQuestionAnswer,
)
from pathfinder.assistant_core.memory.schemas import MemoryValue

__all__ = [
    "CORE_CHECKPOINT_TYPES",
    "build_checkpoint_serde",
    "checkpoint_types",
    "register_checkpoint_types",
]


CORE_CHECKPOINT_TYPES: tuple[type, ...] = (
    TextUIPart,
    ToolApprovalResponded,
    MemoryValue,
    PendingApproval,
    SubAgentApprovalPending,
    SubAgentApprovalCall,
    UserQuestionAnswer,
)

_REGISTERED: list[type] = []


def register_checkpoint_types(*types: type) -> None:
    """Add product state types to the allowlist. Repeat calls add nothing."""
    _REGISTERED.extend(t for t in types if t not in _REGISTERED)


def checkpoint_types() -> tuple[type, ...]:
    """The core types plus everything a product module registered."""
    return (*CORE_CHECKPOINT_TYPES, *_REGISTERED)


def build_checkpoint_serde() -> JsonPlusSerializer:
    """A serializer that can decode allowlisted state under strict msgpack."""
    return JsonPlusSerializer().with_msgpack_allowlist(checkpoint_types())
