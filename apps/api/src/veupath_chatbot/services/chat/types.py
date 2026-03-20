"""Value-object types for the chat service layer."""

from dataclasses import dataclass
from uuid import UUID

from veupath_chatbot.persistence.repositories import StreamRepository, UserRepository
from veupath_chatbot.platform.types import ModelProvider, ReasoningEffort


@dataclass
class ChatContext:
    """Auth and persistence context for a chat turn."""

    user_id: UUID
    user_repo: UserRepository
    stream_repo: StreamRepository


@dataclass
class ChatTurnConfig:
    """Per-turn configuration for a chat operation."""

    mentions: list[dict[str, str]] | None = None
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
