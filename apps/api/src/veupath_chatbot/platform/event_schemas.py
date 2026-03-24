"""SSE event payload schemas — typed Pydantic models for every SSE event.

These live in ``platform`` (not ``transport``) because they are consumed by
services, AI orchestration, and the platform event-sourcing layer — not just
HTTP handlers.  Keeping them here respects the layering rule that lower layers
never import from transport.
"""

from pydantic import Field

from veupath_chatbot.platform.pydantic_base import CamelModel
from veupath_chatbot.platform.types import JSONObject

# ── Message lifecycle ────────────────────────────────────────────────


class MessageStartEventData(CamelModel):
    """Payload for ``message_start`` SSE events."""

    strategy_id: str | None = None
    strategy: JSONObject | None = None


class UserMessageEventData(CamelModel):
    """Payload for ``user_message`` SSE events."""

    message_id: str | None = None
    content: str | None = None


class AssistantDeltaEventData(CamelModel):
    """Payload for ``assistant_delta`` SSE events (streaming tokens)."""

    message_id: str | None = None
    delta: str | None = None


class AssistantMessageEventData(CamelModel):
    """Payload for ``assistant_message`` SSE events (complete message)."""

    message_id: str | None = None
    content: str | None = None


class MessageEndEventData(CamelModel):
    """Payload for ``message_end`` SSE events — mirrors TokenUsageResponse."""

    model_id: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    cached_tokens: int | None = None
    tool_call_count: int | None = None
    registered_tool_count: int | None = None
    llm_call_count: int | None = None
    sub_kani_prompt_tokens: int | None = None
    sub_kani_completion_tokens: int | None = None
    sub_kani_call_count: int | None = None
    estimated_cost_usd: float | None = None


# ── Tool calls ───────────────────────────────────────────────────────


class ToolCallStartEventData(CamelModel):
    """Payload for ``tool_call_start`` SSE events."""

    id: str
    name: str
    arguments: JSONObject = Field(default_factory=dict)


class ToolCallEndEventData(CamelModel):
    """Payload for ``tool_call_end`` SSE events."""

    id: str
    result: str | None = None


# ── Sub-kani events ──────────────────────────────────────────────────


class SubKaniTaskStartEventData(CamelModel):
    """Payload for ``subkani_task_start`` SSE events."""

    task: str | None = None
    model_id: str | None = None


class SubKaniToolCallStartEventData(ToolCallStartEventData):
    """Payload for ``subkani_tool_call_start`` SSE events."""

    task: str | None = None


class SubKaniToolCallEndEventData(ToolCallEndEventData):
    """Payload for ``subkani_tool_call_end`` SSE events."""

    task: str | None = None


class SubKaniTaskEndEventData(CamelModel):
    """Payload for ``subkani_task_end`` SSE events."""

    task: str | None = None
    status: str | None = None
    model_id: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    llm_call_count: int | None = None
    estimated_cost_usd: float | None = None


class SubKaniTaskRetryEventData(CamelModel):
    """Payload for ``subkani_task_retry`` SSE events."""

    task: str | None = None
    attempt: int | None = None


# ── Token usage / model selection ────────────────────────────────────


class TokenUsagePartialEventData(CamelModel):
    """Payload for ``token_usage_partial`` SSE events."""

    prompt_tokens: int | None = None
    registered_tool_count: int | None = None


class ModelSelectedEventData(CamelModel):
    """Payload for ``model_selected`` SSE events."""

    model_id: str


# ── Error ────────────────────────────────────────────────────────────


class ErrorEventData(CamelModel):
    """Payload for ``error`` SSE events."""

    error: str


# ── Strategy / graph events ──────────────────────────────────────────


class GraphSnapshotContent(CamelModel):
    """Content of a graph_snapshot event payload."""

    graph_id: str | None = None
    graph_name: str | None = None
    record_type: str | None = None
    name: str | None = None
    description: str | None = None
    root_step_id: str | None = None
    steps: list[JSONObject] = Field(default_factory=list)
    edges: list[JSONObject] = Field(default_factory=list)
    plan: JSONObject | None = None


class GraphSnapshotEventData(CamelModel):
    """Payload for ``graph_snapshot`` SSE events."""

    graph_snapshot: GraphSnapshotContent | None = None


class StrategyMetaEventData(CamelModel):
    """Payload for ``strategy_meta`` SSE events."""

    graph_id: str | None = None
    graph_name: str | None = None
    name: str | None = None
    description: str | None = None
    record_type: str | None = None


class GraphPlanEventData(CamelModel):
    """Payload for ``graph_plan`` SSE events."""

    graph_id: str | None = None
    plan: JSONObject | None = None
    name: str | None = None
    record_type: str | None = None
    description: str | None = None


class StrategyUpdateEventData(CamelModel):
    """Payload for ``strategy_update`` SSE events.

    ``all_steps`` is ``list[JSONObject]`` (pre-serialized StepResponse dicts)
    to avoid coupling this platform-level schema to service-layer types.
    """

    graph_id: str | None = None
    step: JSONObject | None = None
    all_steps: list[JSONObject] = Field(default_factory=list)


class StrategyLinkEventData(CamelModel):
    """Payload for ``strategy_link`` SSE events."""

    graph_id: str | None = None
    wdk_strategy_id: int | None = None
    wdk_url: str | None = None
    name: str | None = None
    description: str | None = None
    is_saved: bool | None = None


class GraphClearedEventData(CamelModel):
    """Payload for ``graph_cleared`` SSE events."""

    graph_id: str | None = None


class ExecutorBuildRequestEventData(CamelModel):
    """Payload for ``executor_build_request`` SSE events."""

    executor_build_request: JSONObject | None = None


# ── Workbench gene sets ──────────────────────────────────────────────


class GeneSetSummary(CamelModel):
    """Summary of a gene set — nested model, not a top-level event."""

    id: str | None = None
    name: str | None = None
    gene_count: int | None = None
    source: str | None = None
    site_id: str | None = None


class WorkbenchGeneSetEventData(CamelModel):
    """Payload for ``workbench_gene_set`` SSE events."""

    gene_set: GeneSetSummary | None = None


# ── Miscellaneous events ────────────────────────────────────────────


class ReasoningEventData(CamelModel):
    """Payload for ``reasoning`` SSE events."""

    reasoning: str | None = None
