"""Event sourcing core: emit events to Redis + project to PostgreSQL."""

import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import cast

from redis.asyncio import Redis
from shared_py.defaults import DEFAULT_STREAM_NAME
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from veupath_chatbot.domain.strategy.plan_ast import count_plan_nodes
from veupath_chatbot.persistence.models import StreamProjection
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.transport.http.schemas.sse import (
    AssistantMessageEventData,
    GraphPlanEventData,
    GraphSnapshotEventData,
    MessageEndEventData,
    ModelSelectedEventData,
    ReasoningEventData,
    StrategyLinkEventData,
    StrategyMetaEventData,
    SubKaniTaskEndEventData,
    SubKaniTaskStartEventData,
    SubKaniToolCallEndEventData,
    SubKaniToolCallStartEventData,
    ToolCallEndEventData,
    ToolCallStartEventData,
    UserMessageEventData,
)

logger = get_logger(__name__)



# ---------------------------------------------------------------------------
# Event emission
# ---------------------------------------------------------------------------

# Event types where the PostgreSQL projection MUST survive crashes.
# After projecting one of these, we commit immediately so that Redis
# and PostgreSQL stay consistent even if the process dies mid-stream.
_COMMIT_AFTER = frozenset(
    {
        "strategy_link",
        "graph_snapshot",
        "graph_plan",
        "model_selected",
    }
)


async def emit(
    redis: Redis,
    stream_id: str,
    operation_id: str | None,
    event_type: str,
    event_data: JSONObject,
    *,
    session: AsyncSession | None = None,
) -> str:
    """Append an event to a Redis Stream and optionally project to PostgreSQL.

    Returns the Redis entry ID (e.g. '1709234567890-0').
    """
    entry_id_bytes: bytes = await redis.xadd(
        f"stream:{stream_id}",
        {
            "op": (operation_id or "").encode(),
            "type": event_type.encode(),
            "data": json.dumps(event_data, default=str).encode(),
        },
    )
    entry_id = (
        entry_id_bytes.decode()
        if isinstance(entry_id_bytes, bytes)
        else str(entry_id_bytes)
    )

    if session:
        await _project_event(session, stream_id, event_type, event_data, entry_id)
        if event_type in _COMMIT_AFTER:
            await session.commit()

    return entry_id


# ---------------------------------------------------------------------------
# PostgreSQL projection — per-type handlers
# ---------------------------------------------------------------------------

# Event types that update the PostgreSQL projection.  High-frequency
# streaming events (assistant_delta, tool_call_*, subkani_*, etc.) are
# skipped to avoid a DB round-trip per token.
_PROJECTED_EVENT_TYPES = frozenset(
    {
        "user_message",
        "assistant_message",
        "strategy_meta",
        "strategy_link",
        "graph_snapshot",
        "graph_plan",
        "model_selected",
        "graph_cleared",
    }
)


def _project_strategy_meta(updates: dict[str, object], data: JSONObject) -> None:
    event = StrategyMetaEventData.model_validate(data)
    if event.name:
        updates["name"] = event.name
    if event.record_type:
        updates["record_type"] = event.record_type


def _project_strategy_link(updates: dict[str, object], data: JSONObject) -> None:
    event = StrategyLinkEventData.model_validate(data)
    if event.wdk_strategy_id is not None:
        updates["wdk_strategy_id"] = event.wdk_strategy_id
    if event.is_saved is not None:
        updates["is_saved"] = event.is_saved


def _project_graph_snapshot(updates: dict[str, object], data: JSONObject) -> None:
    event = GraphSnapshotEventData.model_validate(data)
    if not event.graph_snapshot:
        return
    snapshot = event.graph_snapshot
    if snapshot.steps:
        updates["step_count"] = len(snapshot.steps)
    if snapshot.root_step_id:
        updates["root_step_id"] = snapshot.root_step_id
    name = snapshot.name or snapshot.graph_name
    if name:
        updates["name"] = name
    if snapshot.record_type:
        updates["record_type"] = snapshot.record_type
    if snapshot.plan:
        updates["plan"] = snapshot.plan


def _project_graph_plan(updates: dict[str, object], data: JSONObject) -> None:
    event = GraphPlanEventData.model_validate(data)
    if event.plan:
        updates["plan"] = event.plan
        updates["step_count"] = count_plan_nodes(event.plan)
    if event.name:
        updates["name"] = event.name
    if event.record_type:
        updates["record_type"] = event.record_type


def _project_model_selected(updates: dict[str, object], data: JSONObject) -> None:
    event = ModelSelectedEventData.model_validate(data)
    updates["model_id"] = event.model_id


def _project_graph_cleared(updates: dict[str, object]) -> None:
    updates["name"] = DEFAULT_STREAM_NAME
    updates["plan"] = {}
    updates["root_step_id"] = None
    updates["step_count"] = 0
    updates["wdk_strategy_id"] = None
    updates["is_saved"] = False


# Dispatch table for handlers that take (updates, data).
_PROJECTION_HANDLERS: dict[str, Callable[[dict[str, object], JSONObject], None]] = {
    "strategy_meta": _project_strategy_meta,
    "strategy_link": _project_strategy_link,
    "graph_snapshot": _project_graph_snapshot,
    "graph_plan": _project_graph_plan,
    "model_selected": _project_model_selected,
}


async def _project_event(
    session: AsyncSession,
    stream_id: str,
    event_type: str,
    event_data: JSONObject,
    entry_id: str,
) -> None:
    """Update the PostgreSQL projection based on an event.

    This is the ONLY code path that writes to stream_projections.
    """
    if event_type not in _PROJECTED_EVENT_TYPES:
        return

    updates: dict[str, object] = {
        "last_event_id": entry_id,
        "updated_at": datetime.now(UTC),
    }

    if event_type in ("user_message", "assistant_message"):
        updates["message_count"] = StreamProjection.__table__.c.message_count + 1
    elif event_type == "graph_cleared":
        _project_graph_cleared(updates)
    else:
        handler = _PROJECTION_HANDLERS.get(event_type)
        if handler:
            handler(updates, event_data)

    # Pre-clear conflicting wdk_strategy_id before the main update.
    # WDK can reuse strategy IDs (same user, same search), so when
    # a new stream claims a WDK ID, the old owner must release it.
    if event_type == "strategy_link" and "wdk_strategy_id" in updates:
        wdk_id = updates["wdk_strategy_id"]
        clear_stmt = (
            update(StreamProjection)
            .where(StreamProjection.wdk_strategy_id == wdk_id)
            .where(StreamProjection.stream_id != stream_id)
            .values(wdk_strategy_id=None, is_saved=False)
        )
        await session.execute(clear_stmt)

    stmt = (
        update(StreamProjection)
        .where(StreamProjection.stream_id == stream_id)
        .values(**updates)
    )
    try:
        await session.execute(stmt)
        await session.flush()
    except Exception as exc:
        # Handle wdk_strategy_id unique constraint race: two concurrent workers
        # auto-build the same search -> both try to claim the same wdk_strategy_id.
        # The first commit wins; the second gets IntegrityError. Clear the old
        # owner and retry.
        if "ix_proj_wdk" in str(exc) and "wdk_strategy_id" in updates:
            await session.rollback()
            wdk_id = cast("int", updates["wdk_strategy_id"])
            clear_stmt = (
                update(StreamProjection)
                .where(StreamProjection.wdk_strategy_id == wdk_id)
                .where(StreamProjection.stream_id != stream_id)
                .values(wdk_strategy_id=None, is_saved=False)
            )
            await session.execute(clear_stmt)
            await session.execute(stmt)
            await session.flush()
        else:
            raise


# ---------------------------------------------------------------------------
# Stream reconstruction
# ---------------------------------------------------------------------------


def _entry_id_to_iso(entry_id: bytes | str) -> str:
    """Convert a Redis stream entry ID (e.g. '1709234567890-0') to ISO 8601."""
    raw = entry_id.decode() if isinstance(entry_id, bytes) else str(entry_id)
    ms_str = raw.split("-")[0]
    try:
        ts = datetime.fromtimestamp(int(ms_str) / 1000, tz=UTC)
    except ValueError, OSError:
        ts = datetime.now(UTC)
    return ts.isoformat()


class _TurnAccumulator:
    """Accumulates metadata for a single assistant turn."""

    __slots__ = (
        "citations",
        "model_id",
        "planning_artifacts",
        "reasoning",
        "subkani_calls",
        "subkani_models",
        "subkani_status",
        "subkani_token_usage",
        "tool_calls",
    )

    def __init__(self) -> None:
        self.tool_calls: list[JSONObject] = []
        self.citations: list[JSONObject] = []
        self.planning_artifacts: list[JSONObject] = []
        self.reasoning: str | None = None
        self.model_id: str | None = None
        self.subkani_calls: dict[str, list[JSONObject]] = {}
        self.subkani_status: dict[str, str] = {}
        self.subkani_models: dict[str, str] = {}
        self.subkani_token_usage: dict[str, JSONObject] = {}

    def reset(self) -> None:
        self.tool_calls.clear()
        self.citations.clear()
        self.planning_artifacts.clear()
        self.reasoning = None
        self.model_id = None
        self.subkani_calls.clear()
        self.subkani_status.clear()
        self.subkani_models.clear()
        self.subkani_token_usage.clear()

    def _build_subkani_activity(self) -> JSONObject:
        """Build subkani activity summary from accumulated state."""
        activity: JSONObject = {
            "calls": {k: list(v) for k, v in self.subkani_calls.items()},
            "status": dict(self.subkani_status),
        }
        if self.subkani_models:
            activity["models"] = dict(self.subkani_models)
        if self.subkani_token_usage:
            activity["tokenUsage"] = dict(self.subkani_token_usage)
        return activity

    def build_assistant_message(
        self,
        data: JSONObject,
        entry_id: bytes | str,
    ) -> JSONObject:
        """Build a complete assistant message with accumulated metadata."""
        event = AssistantMessageEventData.model_validate(data)
        msg: JSONObject = {
            "role": "assistant",
            "content": event.content or "",
            "messageId": event.message_id,
            "timestamp": _entry_id_to_iso(entry_id),
        }
        if self.model_id:
            msg["modelId"] = self.model_id
        if self.tool_calls:
            msg["toolCalls"] = list(self.tool_calls)
        if self.citations:
            msg["citations"] = list(self.citations)
        if self.planning_artifacts:
            msg["planningArtifacts"] = list(self.planning_artifacts)
        if self.reasoning:
            msg["reasoning"] = self.reasoning
        if self.subkani_calls:
            msg["subKaniActivity"] = self._build_subkani_activity()
        # Preserve any fields directly on the event data.
        for key in ("citations", "planningArtifacts", "toolCalls", "reasoning"):
            if key in data and key not in msg:
                msg[key] = data[key]
        return msg


def _handle_user_message(
    data: JSONObject,
    entry_id: bytes | str,
    turn: _TurnAccumulator,
    messages: list[JSONObject],
) -> None:
    event = UserMessageEventData.model_validate(data)
    messages.append(
        {
            "role": "user",
            "content": event.content or "",
            "messageId": event.message_id,
            "timestamp": _entry_id_to_iso(entry_id),
        }
    )


def _handle_tool_call_start(
    data: JSONObject,
    entry_id: bytes | str,
    turn: _TurnAccumulator,
    messages: list[JSONObject],
) -> None:
    # Arguments arrive from Redis as either a JSON string or an
    event = ToolCallStartEventData.model_validate(data)
    turn.tool_calls.append(
        {
            "id": event.id,
            "name": event.name,
            "arguments": event.arguments or {},
        }
    )


def _handle_tool_call_end(
    data: JSONObject,
    entry_id: bytes | str,
    turn: _TurnAccumulator,
    messages: list[JSONObject],
) -> None:
    event = ToolCallEndEventData.model_validate(data)
    for tc in turn.tool_calls:
        if tc["id"] == event.id:
            tc["result"] = event.result
            break


# Citations and planning artifacts use pass-through extraction because their
# SSE models (CitationsEventData, PlanningArtifactEventData) validate nested
# items through strict inner models (CitationResponse, PlanningArtifactResponse)
# that require fields not always present in Redis replay data.  The stream
# reconstruction only accumulates these for later inclusion in the assistant
# message — no field mapping needed.
def _handle_citations(
    data: JSONObject,
    entry_id: bytes | str,
    turn: _TurnAccumulator,
    messages: list[JSONObject],
) -> None:
    cites = data.get("citations")
    if isinstance(cites, list):
        turn.citations.extend(c for c in cites if isinstance(c, dict))


def _handle_planning_artifact(
    data: JSONObject,
    entry_id: bytes | str,
    turn: _TurnAccumulator,
    messages: list[JSONObject],
) -> None:
    artifact = data.get("planningArtifact")
    if isinstance(artifact, dict):
        turn.planning_artifacts.append(artifact)


def _handle_reasoning(
    data: JSONObject,
    entry_id: bytes | str,
    turn: _TurnAccumulator,
    messages: list[JSONObject],
) -> None:
    event = ReasoningEventData.model_validate(data)
    if event.reasoning:
        turn.reasoning = event.reasoning


def _handle_model_selected(
    data: JSONObject,
    entry_id: bytes | str,
    turn: _TurnAccumulator,
    messages: list[JSONObject],
) -> None:
    event = ModelSelectedEventData.model_validate(data)
    turn.model_id = event.model_id


def _handle_subkani_tool_call_start(
    data: JSONObject,
    entry_id: bytes | str,
    turn: _TurnAccumulator,
    messages: list[JSONObject],
) -> None:
    event = SubKaniToolCallStartEventData.model_validate(data)
    task = event.task or ""
    if task:
        turn.subkani_calls.setdefault(task, []).append(
            {
                "id": event.id,
                "name": event.name,
                "arguments": event.arguments or {},
            }
        )


def _handle_subkani_tool_call_end(
    data: JSONObject,
    entry_id: bytes | str,
    turn: _TurnAccumulator,
    messages: list[JSONObject],
) -> None:
    event = SubKaniToolCallEndEventData.model_validate(data)
    task = event.task or ""
    for tc in turn.subkani_calls.get(task, []):
        if tc["id"] == event.id:
            tc["result"] = event.result
            break


def _handle_assistant_message(
    data: JSONObject,
    entry_id: bytes | str,
    turn: _TurnAccumulator,
    messages: list[JSONObject],
) -> None:
    messages.append(turn.build_assistant_message(data, entry_id))


# Type alias for stream event handler functions.
type _StreamEventHandler = Callable[
    [JSONObject, bytes | str, _TurnAccumulator, list[JSONObject]], None
]

# Dispatch table for stream reconstruction event handlers.
_STREAM_EVENT_HANDLERS: dict[str, _StreamEventHandler] = {
    "user_message": _handle_user_message,
    "tool_call_start": _handle_tool_call_start,
    "tool_call_end": _handle_tool_call_end,
    "citations": _handle_citations,
    "planning_artifact": _handle_planning_artifact,
    "reasoning": _handle_reasoning,
    "model_selected": _handle_model_selected,
    "subkani_tool_call_start": _handle_subkani_tool_call_start,
    "subkani_tool_call_end": _handle_subkani_tool_call_end,
    "assistant_message": _handle_assistant_message,
}


def _process_stream_event(
    event_type: str,
    data: JSONObject,
    entry_id: bytes | str,
    turn: _TurnAccumulator,
    messages: list[JSONObject],
) -> None:
    """Process a single Redis stream event, mutating *turn* and *messages*.

    Uses a dispatch table for most event types; a few special cases
    (message_start, subkani_task_start/end, message_end) that need the
    turn/messages pair in non-standard ways are handled inline.
    """
    if event_type == "message_start":
        turn.reset()
        return

    if event_type == "subkani_task_start":
        _handle_subkani_task_start(turn, data)
        return

    if event_type == "subkani_task_end":
        _handle_subkani_task_end(turn, data)
        return

    if event_type == "message_end":
        _handle_message_end(data, messages, turn)
        return

    handler = _STREAM_EVENT_HANDLERS.get(event_type)
    if handler:
        handler(data, entry_id, turn, messages)


def _handle_subkani_task_start(turn: _TurnAccumulator, data: JSONObject) -> None:
    """Process a subkani_task_start event."""
    event = SubKaniTaskStartEventData.model_validate(data)
    task = event.task or ""
    if task:
        turn.subkani_status[task] = "running"
        turn.subkani_calls.setdefault(task, [])
        if event.model_id:
            turn.subkani_models[task] = event.model_id


def _handle_subkani_task_end(turn: _TurnAccumulator, data: JSONObject) -> None:
    """Process a subkani_task_end event, capturing token usage."""
    event = SubKaniTaskEndEventData.model_validate(data)
    task = event.task or ""
    if not task:
        return
    turn.subkani_status[task] = event.status or "done"
    if event.model_id:
        turn.subkani_models[task] = event.model_id
    if event.prompt_tokens is not None:
        turn.subkani_token_usage[task] = {
            "promptTokens": event.prompt_tokens or 0,
            "completionTokens": event.completion_tokens or 0,
            "llmCallCount": event.llm_call_count or 0,
            "estimatedCostUsd": event.estimated_cost_usd or 0.0,
        }


def _handle_message_end(
    data: JSONObject, messages: list[JSONObject], turn: _TurnAccumulator
) -> None:
    """Process a message_end event, attaching token usage to messages."""
    event = MessageEndEventData.model_validate(data)
    total = event.total_tokens or 0
    if total > 0:
        token_usage: JSONObject = {
            "promptTokens": event.prompt_tokens or 0,
            "completionTokens": event.completion_tokens or 0,
            "totalTokens": total,
            "cachedTokens": event.cached_tokens or 0,
            "toolCallCount": event.tool_call_count or 0,
            "registeredToolCount": event.registered_tool_count or 0,
            "llmCallCount": event.llm_call_count or 0,
            "subKaniPromptTokens": event.sub_kani_prompt_tokens or 0,
            "subKaniCompletionTokens": event.sub_kani_completion_tokens or 0,
            "subKaniCallCount": event.sub_kani_call_count or 0,
            "estimatedCostUsd": event.estimated_cost_usd or 0.0,
            "modelId": event.model_id or "",
        }
        for i in range(len(messages) - 1, -1, -1):
            if messages[i]["role"] == "user" and "tokenUsage" not in messages[i]:
                messages[i]["tokenUsage"] = token_usage
                break
        for i in range(len(messages) - 1, -1, -1):
            if messages[i]["role"] == "assistant" and "tokenUsage" not in messages[i]:
                messages[i]["tokenUsage"] = token_usage
                break
    turn.reset()


async def read_stream_messages(redis: Redis, stream_id: str) -> list[JSONObject]:
    """Read all user + assistant messages from a Redis stream.

    Aggregates metadata from surrounding events (tool_call_start/end,
    citations, planning_artifact, reasoning, subkani events) into each
    assistant_message so the full conversation context survives refresh.

    Used by the GET /strategies/{id} endpoint to return chat history.
    """
    entries = await redis.xrange(f"stream:{stream_id}")
    messages: list[JSONObject] = []
    turn = _TurnAccumulator()

    for entry_id, fields in entries:
        event_type = fields.get(b"type", b"").decode()
        try:
            data = json.loads(fields[b"data"])
        except json.JSONDecodeError, KeyError:
            continue

        _process_stream_event(event_type, data, entry_id, turn, messages)

    return messages


def _collect_open_tool_calls(
    entries: list[tuple[bytes | str, dict[bytes, bytes]]],
    start_idx: int,
) -> dict[str, JSONObject]:
    """Collect tool calls that have started but not ended since *start_idx*."""
    open_tools: dict[str, JSONObject] = {}
    for _eid, fields in entries[start_idx:]:
        event_type = fields.get(b"type", b"").decode()
        if event_type == "tool_call_start":
            try:
                data = json.loads(fields[b"data"])
                start = ToolCallStartEventData.model_validate(data)
                open_tools[start.id] = {
                    "id": start.id,
                    "name": start.name,
                    "arguments": start.arguments,
                }
            except json.JSONDecodeError, KeyError, ValueError:
                pass
        elif event_type == "tool_call_end":
            try:
                data = json.loads(fields[b"data"])
                end = ToolCallEndEventData.model_validate(data)
                open_tools.pop(end.id, None)
            except json.JSONDecodeError, KeyError, ValueError:
                pass
    return open_tools


async def read_stream_thinking(redis: Redis, stream_id: str) -> JSONObject | None:
    """Derive in-progress thinking state from stream events.

    Thinking = tool_call_start events without matching tool_call_end,
    from the most recent active operation.
    """
    entries = await redis.xrange(f"stream:{stream_id}")

    # Find the last message_start (marks beginning of a turn)
    last_start_idx = -1
    for i, (_eid, fields) in enumerate(entries):
        if fields.get(b"type", b"") == b"message_start":
            last_start_idx = i

    if last_start_idx < 0:
        return None

    # Check if this turn is still active (no message_end after last start)
    has_end = any(
        fields.get(b"type", b"") == b"message_end"
        for _eid, fields in entries[last_start_idx:]
    )
    if has_end:
        return None

    open_tools = _collect_open_tool_calls(entries, last_start_idx)
    if not open_tools:
        return None

    return {
        "toolCalls": list(open_tools.values()),
    }
