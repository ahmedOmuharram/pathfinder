"""SSE event payload schemas — typed Pydantic models for every SSE event."""

from pydantic import BaseModel, Field

from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.transport.http.schemas.chat import (
    CitationResponse,
    PlanningArtifactResponse,
)

# ── Message lifecycle ────────────────────────────────────────────────


class MessageStartEventData(BaseModel):
    """Payload for ``message_start`` SSE events."""

    strategy_id: str | None = Field(default=None, alias="strategyId")
    strategy: JSONObject | None = None

    model_config = {"populate_by_name": True}


class UserMessageEventData(BaseModel):
    """Payload for ``user_message`` SSE events."""

    message_id: str | None = Field(default=None, alias="messageId")
    content: str | None = None

    model_config = {"populate_by_name": True}


class AssistantDeltaEventData(BaseModel):
    """Payload for ``assistant_delta`` SSE events (streaming tokens)."""

    message_id: str | None = Field(default=None, alias="messageId")
    delta: str | None = None

    model_config = {"populate_by_name": True}


class AssistantMessageEventData(BaseModel):
    """Payload for ``assistant_message`` SSE events (complete message)."""

    message_id: str | None = Field(default=None, alias="messageId")
    content: str | None = None

    model_config = {"populate_by_name": True}


class MessageEndEventData(BaseModel):
    """Payload for ``message_end`` SSE events — mirrors TokenUsageResponse."""

    model_id: str | None = Field(default=None, alias="modelId")
    prompt_tokens: int | None = Field(default=None, alias="promptTokens")
    completion_tokens: int | None = Field(default=None, alias="completionTokens")
    total_tokens: int | None = Field(default=None, alias="totalTokens")
    cached_tokens: int | None = Field(default=None, alias="cachedTokens")
    tool_call_count: int | None = Field(default=None, alias="toolCallCount")
    registered_tool_count: int | None = Field(default=None, alias="registeredToolCount")
    llm_call_count: int | None = Field(default=None, alias="llmCallCount")
    sub_kani_prompt_tokens: int | None = Field(
        default=None, alias="subKaniPromptTokens"
    )
    sub_kani_completion_tokens: int | None = Field(
        default=None, alias="subKaniCompletionTokens"
    )
    sub_kani_call_count: int | None = Field(default=None, alias="subKaniCallCount")
    estimated_cost_usd: float | None = Field(default=None, alias="estimatedCostUsd")

    model_config = {"populate_by_name": True}


# ── Tool calls ───────────────────────────────────────────────────────


class ToolCallStartEventData(BaseModel):
    """Payload for ``tool_call_start`` SSE events."""

    id: str
    name: str
    arguments: str | None = None

    model_config = {"populate_by_name": True}


class ToolCallEndEventData(BaseModel):
    """Payload for ``tool_call_end`` SSE events."""

    id: str
    result: str | None = None

    model_config = {"populate_by_name": True}


# ── Sub-kani events ──────────────────────────────────────────────────


class SubKaniTaskStartEventData(BaseModel):
    """Payload for ``subkani_task_start`` SSE events."""

    task: str | None = None
    model_id: str | None = Field(default=None, alias="modelId")

    model_config = {"populate_by_name": True}


class SubKaniToolCallStartEventData(BaseModel):
    """Payload for ``subkani_tool_call_start`` SSE events."""

    task: str | None = None
    id: str
    name: str
    arguments: str | None = None

    model_config = {"populate_by_name": True}


class SubKaniToolCallEndEventData(BaseModel):
    """Payload for ``subkani_tool_call_end`` SSE events."""

    task: str | None = None
    id: str
    result: str | None = None

    model_config = {"populate_by_name": True}


class SubKaniTaskEndEventData(BaseModel):
    """Payload for ``subkani_task_end`` SSE events."""

    task: str | None = None
    status: str | None = None
    model_id: str | None = Field(default=None, alias="modelId")
    prompt_tokens: int | None = Field(default=None, alias="promptTokens")
    completion_tokens: int | None = Field(default=None, alias="completionTokens")
    llm_call_count: int | None = Field(default=None, alias="llmCallCount")
    estimated_cost_usd: float | None = Field(default=None, alias="estimatedCostUsd")

    model_config = {"populate_by_name": True}


# ── Token usage / model selection ────────────────────────────────────


class TokenUsagePartialEventData(BaseModel):
    """Payload for ``token_usage_partial`` SSE events."""

    prompt_tokens: int | None = Field(default=None, alias="promptTokens")
    registered_tool_count: int | None = Field(default=None, alias="registeredToolCount")

    model_config = {"populate_by_name": True}


class ModelSelectedEventData(BaseModel):
    """Payload for ``model_selected`` SSE events."""

    model_id: str = Field(alias="modelId")

    model_config = {"populate_by_name": True}


# ── Optimization events (imported from optimization.py) ─────────────
# OptimizationTrialData, OptimizationParameterSpecData, and
# OptimizationProgressEventData are re-exported from the import above.


# ── Error ────────────────────────────────────────────────────────────


class ErrorEventData(BaseModel):
    """Payload for ``error`` SSE events."""

    error: str

    model_config = {"populate_by_name": True}


# ── Strategy / graph events ──────────────────────────────────────────


class GraphSnapshotEventData(BaseModel):
    """Payload for ``graph_snapshot`` SSE events."""

    graph_snapshot: JSONObject | None = Field(default=None, alias="graphSnapshot")

    model_config = {"populate_by_name": True}


class StrategyMetaEventData(BaseModel):
    """Payload for ``strategy_meta`` SSE events."""

    graph_id: str | None = Field(default=None, alias="graphId")
    graph_name: str | None = Field(default=None, alias="graphName")
    name: str | None = None
    description: str | None = None
    record_type: str | None = Field(default=None, alias="recordType")

    model_config = {"populate_by_name": True}


class GraphPlanEventData(BaseModel):
    """Payload for ``graph_plan`` SSE events."""

    graph_id: str | None = Field(default=None, alias="graphId")
    plan: JSONObject | None = None
    name: str | None = None
    record_type: str | None = Field(default=None, alias="recordType")
    description: str | None = None

    model_config = {"populate_by_name": True}


class StrategyUpdateEventData(BaseModel):
    """Payload for ``strategy_update`` SSE events."""

    graph_id: str | None = Field(default=None, alias="graphId")
    step: JSONObject | None = None

    model_config = {"populate_by_name": True}


class StrategyLinkEventData(BaseModel):
    """Payload for ``strategy_link`` SSE events."""

    graph_id: str | None = Field(default=None, alias="graphId")
    wdk_strategy_id: int | None = Field(default=None, alias="wdkStrategyId")
    wdk_url: str | None = Field(default=None, alias="wdkUrl")
    name: str | None = None
    description: str | None = None
    is_saved: bool | None = Field(default=None, alias="isSaved")

    model_config = {"populate_by_name": True}


class GraphClearedEventData(BaseModel):
    """Payload for ``graph_cleared`` SSE events."""

    graph_id: str | None = Field(default=None, alias="graphId")

    model_config = {"populate_by_name": True}


class ExecutorBuildRequestEventData(BaseModel):
    """Payload for ``executor_build_request`` SSE events."""

    executor_build_request: JSONObject | None = Field(
        default=None, alias="executorBuildRequest"
    )

    model_config = {"populate_by_name": True}


# ── Workbench gene sets ──────────────────────────────────────────────


class GeneSetSummary(BaseModel):
    """Summary of a gene set — nested model, not a top-level event."""

    id: str | None = None
    name: str | None = None
    gene_count: int | None = Field(default=None, alias="geneCount")
    source: str | None = None
    site_id: str | None = Field(default=None, alias="siteId")

    model_config = {"populate_by_name": True}


class WorkbenchGeneSetEventData(BaseModel):
    """Payload for ``workbench_gene_set`` SSE events."""

    gene_set: GeneSetSummary | None = Field(default=None, alias="geneSet")

    model_config = {"populate_by_name": True}


# ── Miscellaneous events ────────────────────────────────────────────


class CitationsEventData(BaseModel):
    """Payload for ``citations`` SSE events."""

    citations: list[CitationResponse] | None = None

    model_config = {"populate_by_name": True}


class PlanningArtifactEventData(BaseModel):
    """Payload for ``planning_artifact`` SSE events."""

    planning_artifact: PlanningArtifactResponse | None = Field(
        default=None, alias="planningArtifact"
    )

    model_config = {"populate_by_name": True}


class ReasoningEventData(BaseModel):
    """Payload for ``reasoning`` SSE events."""

    reasoning: str | None = None

    model_config = {"populate_by_name": True}
