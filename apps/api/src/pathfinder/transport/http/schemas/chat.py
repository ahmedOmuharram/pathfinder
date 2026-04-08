"""Chat request/response DTOs."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from pathfinder.platform.event_schemas import PipelineConfig
from pathfinder.platform.types import (
    JSONObject,
    JSONValue,
)
from pathfinder.services.chat.types import ChatMention
from pathfinder.services.strategies.schemas import StrategyPlanPayload
from pathfinder.transport.http.schemas.optimization import (
    OptimizationProgressEventData,
)


class ChatRequest(BaseModel):
    """Request to send a chat message."""

    strategy_id: UUID | None = Field(default=None, alias="strategyId")
    site_id: str = Field(alias="siteId")
    message: str = Field(min_length=1, max_length=200_000)

    # Per-phase model configuration (required).
    pipeline: PipelineConfig = Field(alias="pipeline")

    # Thesis experiment controls.
    disable_rag: bool = Field(default=False, alias="disableRag")
    temperature: float | None = Field(default=None)
    seed: int | None = Field(default=None)

    # @-mention references to strategies and experiments.
    mentions: list[ChatMention] = Field(default_factory=list)

    # Structured metadata from UI interactions (e.g. plan approval).
    metadata: dict[str, JSONValue] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


class ToolCallResponse(BaseModel):
    """Tool call information."""

    id: str
    name: str
    arguments: JSONObject
    result: str | None = None


class ThinkingResponse(BaseModel):
    """In-progress tool call state."""

    tool_calls: list[ToolCallResponse] | None = Field(default=None, alias="toolCalls")
    last_tool_calls: list[ToolCallResponse] | None = Field(
        default=None, alias="lastToolCalls"
    )
    reasoning: str | None = None
    updated_at: datetime | None = Field(default=None, alias="updatedAt")

    model_config = {"populate_by_name": True}


class TokenUsageResponse(BaseModel):
    """Token usage statistics for a message turn."""

    prompt_tokens: int = Field(alias="promptTokens")
    completion_tokens: int = Field(alias="completionTokens")
    total_tokens: int = Field(alias="totalTokens")
    cached_tokens: int = Field(default=0, alias="cachedTokens")
    tool_call_count: int = Field(alias="toolCallCount")
    registered_tool_count: int = Field(alias="registeredToolCount")
    llm_call_count: int = Field(default=0, alias="llmCallCount")
    estimated_cost_usd: float = Field(default=0.0, alias="estimatedCostUsd")
    model_id: str = Field(default="", alias="modelId")

    model_config = {"populate_by_name": True}


class CitationResponse(BaseModel):
    """Citation from research tools."""

    id: str
    source: str  # "pubmed" | "arxiv" | "google_scholar" | "web"
    tag: str | None = None
    title: str
    url: str | None = None
    authors: list[str] | None = None
    year: int | None = None
    doi: str | None = None
    pmid: str | None = None
    snippet: str | None = None
    accessed_at: str | None = Field(default=None, alias="accessedAt")

    model_config = {"populate_by_name": True}


class PlanningArtifactResponse(BaseModel):
    """Strategy planning artifact."""

    id: str
    title: str
    summary_markdown: str = Field(alias="summaryMarkdown")
    assumptions: list[str] = Field(default_factory=list)
    parameters: dict[str, JSONValue] = Field(default_factory=dict)
    proposed_strategy_plan: StrategyPlanPayload | None = Field(
        default=None, alias="proposedStrategyPlan"
    )
    created_at: str = Field(alias="createdAt")

    model_config = {"populate_by_name": True}


class MessageResponse(BaseModel):
    """Chat message."""

    role: Literal["user", "assistant"]
    content: str
    model_id: str | None = Field(default=None, alias="modelId")
    tool_calls: list[ToolCallResponse] | None = Field(default=None, alias="toolCalls")
    citations: list[CitationResponse] | None = None
    planning_artifacts: list[PlanningArtifactResponse] | None = Field(
        default=None, alias="planningArtifacts"
    )
    reasoning: str | None = Field(default=None)
    optimization_progress: OptimizationProgressEventData | None = Field(
        default=None, alias="optimizationProgress"
    )
    token_usage: TokenUsageResponse | None = Field(default=None, alias="tokenUsage")
    timestamp: datetime

    model_config = {"populate_by_name": True, "extra": "ignore"}
