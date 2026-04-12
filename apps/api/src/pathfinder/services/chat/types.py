"""Value-object types for the chat service layer."""

from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from pathfinder.domain.strategy.plan_actions import PlanActionContext
from pathfinder.persistence.repositories import StreamRepository, UserRepository
from pathfinder.platform.event_schemas import PipelineConfig
from pathfinder.platform.types import JSONObject, JSONValue

MentionType = Literal["strategy", "experiment"]
type ChatTurnMetadata = dict[str, JSONValue]


def turn_metadata_trace_fields(metadata: ChatTurnMetadata | None) -> JSONObject:
    """Return stable trace fields derived from structured turn metadata."""
    if metadata is None or len(metadata) == 0:
        return {}
    return {
        "turn_metadata": metadata,
        "turn_metadata_keys": sorted(metadata),
        "regenerate_of_trace_id": metadata.get("regenerateOfTraceId"),
        "regenerate_of_message_id": metadata.get("regenerateOfMessageId"),
    }


class ChatMention(BaseModel):
    """A reference to a strategy or experiment included via @-mention."""

    type: MentionType
    id: str
    display_name: str = Field(alias="displayName")

    model_config = {"populate_by_name": True}


@dataclass
class ChatContext:
    """Auth and persistence context for a chat turn."""

    user_id: UUID
    user_repo: UserRepository
    stream_repo: StreamRepository


@dataclass
class TurnIdentity:
    """Immutable identifiers for a single chat turn.

    Groups the per-turn fields that both the producer and the dependency
    builder need, keeping function signatures under the argument limit.
    """

    stream_id_str: str
    site_id: str
    user_id: UUID
    model_message: str


@dataclass
class ChatTurnConfig:
    """Per-turn configuration for a chat operation."""

    pipeline: PipelineConfig | None = None
    mentions: list[ChatMention] | None = None
    plan_action: PlanActionContext | None = None
    metadata: ChatTurnMetadata = field(default_factory=dict)
    # Thesis experiment controls
    disable_rag: bool = False
    temperature: float | None = None
    seed: int | None = None
