"""Checkpoint serializer with an explicit msgpack type allowlist.

LangGraph decodes unregistered types with a deprecation warning today and
will refuse them in a future release. Every type that reaches a checkpoint
must therefore be on the allowlist, or upgrading LangGraph would make
existing conversations unresumable.

Core types are listed here. An assistant declares its own state types on its
``AssistantSpec``; one checkpoint table serves every assistant, so callers
pass the union.
"""

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from pydantic_ai.ui.vercel_ai.request_types import (
    TextUIPart,
    ToolApprovalResponded,
)

from assistant_core.graph.turn_state import (
    PendingApproval,
    SubAgentApprovalCall,
    SubAgentApprovalPending,
    UserQuestionAnswer,
)
from assistant_core.memory.schemas import MemoryValue

__all__ = [
    "CORE_CHECKPOINT_TYPES",
    "build_checkpoint_serde",
    "checkpoint_types",
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


def checkpoint_types(assistant_types: tuple[type, ...] = ()) -> tuple[type, ...]:
    """The core types plus the state types the assistants declare."""
    return (*CORE_CHECKPOINT_TYPES, *(t for t in assistant_types))


def build_checkpoint_serde(
    assistant_types: tuple[type, ...] = (),
) -> JsonPlusSerializer:
    """A serializer that can decode allowlisted state under strict msgpack."""
    return JsonPlusSerializer().with_msgpack_allowlist(
        checkpoint_types(assistant_types),
    )
