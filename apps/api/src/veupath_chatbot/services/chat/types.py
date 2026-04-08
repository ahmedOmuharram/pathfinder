"""Value-object types for the chat service layer."""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from veupath_chatbot.persistence.repositories import StreamRepository, UserRepository
from veupath_chatbot.platform.event_schemas import PipelineConfig

MentionType = Literal["strategy", "experiment"]


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
    # Thesis experiment controls
    disable_rag: bool = False
    temperature: float | None = None
    seed: int | None = None
