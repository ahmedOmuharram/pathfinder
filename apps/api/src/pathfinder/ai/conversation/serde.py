"""Checkpoint serializer with an explicit msgpack type allowlist.

LangGraph decodes unregistered types with a deprecation warning today and
will refuse them in a future release. Every PathFinder type that reaches a
checkpoint must therefore be declared here, or upgrading LangGraph would
make existing conversations unresumable.

Adding a new field to graph state? If its type is a PathFinder model or
enum, add it to :data:`CHECKPOINT_MSGPACK_TYPES` — the strict round-trip
tests in ``tests/unit/ai/conversation/test_checkpoint_serde.py`` fail
otherwise.
"""

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from pydantic_ai.ui.vercel_ai.request_types import TextUIPart

from pathfinder.ai.agents.state import SearchOverview
from pathfinder.ai.graph.state import PhaseDisposition, VerificationDigest
from pathfinder.ai.lead.intent import IntentClassification, UserIntent
from pathfinder.ai.memory.schemas import MemoryValue
from pathfinder.domain.strategy.build_outcome import BuildOutcome, NodeResult
from pathfinder.domain.strategy.constraints import ConstraintKind, ConstraintSource
from pathfinder.domain.strategy.operational_spec import OperationalSpec
from pathfinder.domain.strategy.staleness import StaleBuild

__all__ = ["CHECKPOINT_MSGPACK_TYPES", "build_checkpoint_serde"]


CHECKPOINT_MSGPACK_TYPES: tuple[type, ...] = (
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
    StaleBuild,
    TextUIPart,
)


def build_checkpoint_serde() -> JsonPlusSerializer:
    """A serializer that can decode PathFinder state under strict msgpack."""
    return JsonPlusSerializer().with_msgpack_allowlist(CHECKPOINT_MSGPACK_TYPES)
