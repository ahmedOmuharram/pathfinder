"""Chat request/response DTOs."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from veupath_chatbot.platform.types import (
    JSONArray,
    JSONObject,
    ModelProvider,
    ReasoningEffort,
)
from veupath_chatbot.services.chat.mention_context import MentionType


class ChatMention(BaseModel):
    """A reference to a strategy or experiment included via @-mention."""

    type: MentionType
    id: str
    display_name: str = Field(alias="displayName")

    model_config = {"populate_by_name": True}


class ChatRequest(BaseModel):
    """Request to send a chat message."""

    strategy_id: UUID | None = Field(default=None, alias="strategyId")
    site_id: str = Field(alias="siteId")
    message: str = Field(min_length=1, max_length=200_000)

    # Per-request model overrides (optional; falls back to server defaults).
    provider: ModelProvider | None = Field(default=None)
    model_id: str | None = Field(default=None, alias="model")
    reasoning_effort: ReasoningEffort | None = Field(
        default=None, alias="reasoningEffort"
    )

    # Thesis experiment controls.
    disable_rag: bool = Field(default=False, alias="disableRag")
    temperature: float | None = Field(default=None)
    seed: int | None = Field(default=None)

    # Per-model tuning overrides from user settings.
    context_size: int | None = Field(default=None, alias="contextSize")
    response_tokens: int | None = Field(default=None, alias="responseTokens")
    reasoning_budget: int | None = Field(default=None, alias="reasoningBudget")

    # Tools the user has disabled in the UI.
    disabled_tools: list[str] = Field(default_factory=list, alias="disabledTools")

    # @-mention references to strategies and experiments.
    mentions: list[ChatMention] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class ToolCallResponse(BaseModel):
    """Tool call information."""

    id: str
    name: str
    arguments: JSONObject
    result: str | None = None


class SubKaniActivityResponse(BaseModel):
    """Sub-kani tool call activity."""

    calls: dict[str, list[ToolCallResponse]]
    status: dict[str, str]


class ThinkingResponse(BaseModel):
    """In-progress tool call state."""

    tool_calls: list[ToolCallResponse] | None = Field(default=None, alias="toolCalls")
    last_tool_calls: list[ToolCallResponse] | None = Field(
        default=None, alias="lastToolCalls"
    )
    sub_kani_calls: dict[str, list[ToolCallResponse]] | None = Field(
        default=None, alias="subKaniCalls"
    )
    sub_kani_status: dict[str, str] | None = Field(default=None, alias="subKaniStatus")
    reasoning: str | None = None
    updated_at: datetime | None = Field(default=None, alias="updatedAt")

    model_config = {"populate_by_name": True}


class TokenUsageResponse(BaseModel):
    """Token usage statistics for a message turn."""

    prompt_tokens: int = Field(alias="promptTokens")
    completion_tokens: int = Field(alias="completionTokens")
    total_tokens: int = Field(alias="totalTokens")
    tool_call_count: int = Field(alias="toolCallCount")
    registered_tool_count: int = Field(alias="registeredToolCount")

    model_config = {"populate_by_name": True}


class MessageResponse(BaseModel):
    """Chat message."""

    role: str
    content: str
    tool_calls: list[ToolCallResponse] | None = Field(default=None, alias="toolCalls")
    sub_kani_activity: SubKaniActivityResponse | None = Field(
        default=None, alias="subKaniActivity"
    )
    citations: JSONArray | None = None
    planning_artifacts: JSONArray | None = Field(
        default=None, alias="planningArtifacts"
    )
    reasoning: str | None = Field(default=None)
    optimization_progress: JSONObject | None = Field(
        default=None, alias="optimizationProgress"
    )
    token_usage: TokenUsageResponse | None = Field(default=None, alias="tokenUsage")
    timestamp: datetime

    model_config = {"populate_by_name": True, "extra": "ignore"}
