"""Chat request/response DTOs."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from veupath_chatbot.platform.types import JSONArray, JSONObject

ChatMode = Literal["execute", "plan"]
ModelProvider = Literal["openai", "anthropic", "google"]
ReasoningEffort = Literal["none", "low", "medium", "high"]


class ChatMention(BaseModel):
    """A reference to a strategy or experiment included via @-mention."""

    type: Literal["strategy", "experiment"]
    id: str
    display_name: str = Field(alias="displayName")

    model_config = {"populate_by_name": True}


class ChatRequest(BaseModel):
    """Request to send a chat message."""

    strategy_id: UUID | None = Field(default=None, alias="strategyId")
    plan_session_id: UUID | None = Field(default=None, alias="planSessionId")
    site_id: str = Field(alias="siteId")
    message: str = Field(min_length=1, max_length=200_000)
    mode: ChatMode = Field(default="execute")

    # Per-request model overrides (optional; falls back to server defaults).
    provider: ModelProvider | None = Field(default=None)
    model_id: str | None = Field(default=None, alias="model")
    reasoning_effort: ReasoningEffort | None = Field(
        default=None, alias="reasoningEffort"
    )

    # Optional reference strategy for plan-mode context injection (legacy).
    reference_strategy_id: UUID | None = Field(
        default=None, alias="referenceStrategyId"
    )

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


class MessageResponse(BaseModel):
    """Chat message."""

    role: str
    content: str
    tool_calls: list[ToolCallResponse] | None = Field(default=None, alias="toolCalls")
    sub_kani_activity: SubKaniActivityResponse | None = Field(
        default=None, alias="subKaniActivity"
    )
    mode: ChatMode | None = Field(default=None)
    citations: JSONArray | None = None
    planning_artifacts: JSONArray | None = Field(
        default=None, alias="planningArtifacts"
    )
    reasoning: str | None = Field(default=None)
    optimization_progress: JSONObject | None = Field(
        default=None, alias="optimizationProgress"
    )
    timestamp: datetime

    model_config = {"populate_by_name": True, "extra": "ignore"}
