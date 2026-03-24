"""Value-object types for the chat service layer."""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from veupath_chatbot.persistence.repositories import StreamRepository, UserRepository
from veupath_chatbot.platform.types import ModelProvider, ReasoningEffort

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
class ChatTurnConfig:
    """Per-turn configuration for a chat operation."""

    mentions: list[ChatMention] | None = None
    # Thesis experiment controls
    disable_rag: bool = False
    disabled_tools: list[str] | None = None
    # Engine/model overrides (passed through to EngineConfig)
    provider_override: ModelProvider | None = None
    model_override: str | None = None
    reasoning_effort: ReasoningEffort | None = None
    temperature: float | None = None
    seed: int | None = None
    context_size: int | None = None
    response_tokens: int | None = None
    reasoning_budget: int | None = None
