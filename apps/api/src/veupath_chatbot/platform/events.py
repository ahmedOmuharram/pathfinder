"""Event sourcing core: emit events to Redis + project to PostgreSQL."""

import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import cast

from redis.asyncio import Redis
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from veupath_chatbot.persistence.models import StreamProjection
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Plan AST helpers
# ---------------------------------------------------------------------------


def _steps_to_plan(
    steps: list[JSONObject],
    root_step_id: str,
    snapshot: JSONObject,
) -> JSONObject | None:
    """Build a recursive plan AST from a flat steps list.

    Returns None if the root step cannot be found.
    """
    step_map: dict[str, JSONObject] = {}
    for s in steps:
        sid = s.get("id")
        if isinstance(sid, str):
            step_map[sid] = s

    def build_node(step_id: str) -> JSONObject | None:
        s = step_map.get(step_id)
        if not s:
            return None
        raw_name = s.get("searchName") or ""
        kind = str(s.get("kind") or "").strip().lower()
        search_name = (
            raw_name
            if raw_name
            else (
                "__combine__"
                if kind == "combine" or s.get("operator")
                else "__unknown__"
            )
        )
        node: JSONObject = {
            "id": step_id,
            "searchName": search_name,
            "parameters": s.get("parameters", {}),
        }
        display = s.get("displayName")
        if display:
            node["displayName"] = display
        op = s.get("operator")
        if op:
            node["operator"] = op
        coloc = s.get("colocationParams")
        if coloc:
            node["colocationParams"] = coloc
        primary_id = s.get("primaryInputStepId")
        if isinstance(primary_id, str):
            primary = build_node(primary_id)
            if primary:
                node["primaryInput"] = primary
        secondary_id = s.get("secondaryInputStepId")
        if isinstance(secondary_id, str):
            secondary = build_node(secondary_id)
            if secondary:
                node["secondaryInput"] = secondary
        return node

    root = build_node(root_step_id)
    if not root:
        return None
    return {
        "recordType": snapshot.get("recordType", "transcript"),
        "root": root,
        "metadata": {"name": snapshot.get("name", "")},
    }


def _count_plan_nodes(plan: JSONObject) -> int:
    """Count step nodes in a plan dict by walking the tree.

    The plan dict has ``{"root": {..., "primaryInput": ..., "secondaryInput": ...}}``.
    Each node with a ``searchName`` key counts as a step.
    """
    root = plan.get("root")
    if not isinstance(root, dict):
        return 0

    count = 0

    def visit(node: JSONObject) -> None:
        nonlocal count
        if node.get("searchName"):
            count += 1
        primary = node.get("primaryInput")
        if isinstance(primary, dict):
            visit(primary)
        secondary = node.get("secondaryInput")
        if isinstance(secondary, dict):
            visit(secondary)

    visit(root)
    return count


def _parse_arguments(raw: object) -> JSONObject:
    """Parse tool call arguments into a dict.

    Arguments arrive as JSON strings from Redis but must be dicts for
    ``ToolCallResponse`` validation.  Already-dict values pass through.
    """
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError, ValueError:
            pass
    return {}


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
    name = data.get("name")
    if isinstance(name, str) and name:
        updates["name"] = name
    rt = data.get("recordType")
    if isinstance(rt, str) and rt:
        updates["record_type"] = rt


def _project_strategy_link(updates: dict[str, object], data: JSONObject) -> None:
    wdk_id = data.get("wdkStrategyId")
    if isinstance(wdk_id, int):
        updates["wdk_strategy_id"] = wdk_id
    is_saved = data.get("isSaved")
    if isinstance(is_saved, bool):
        updates["is_saved"] = is_saved


def _project_graph_snapshot(updates: dict[str, object], data: JSONObject) -> None:
    snapshot = data.get("graphSnapshot")
    if not isinstance(snapshot, dict):
        return
    steps = snapshot.get("steps")
    if isinstance(steps, list):
        updates["steps"] = steps
        updates["step_count"] = len(steps)
    root = snapshot.get("rootStepId")
    if isinstance(root, str):
        updates["root_step_id"] = root
    name = snapshot.get("name") or snapshot.get("graphName")
    if isinstance(name, str) and name:
        updates["name"] = name
    rt = snapshot.get("recordType")
    if isinstance(rt, str) and rt:
        updates["record_type"] = rt
    # Build the plan AST from the flat steps when we have a root step ID.
    # This covers the case where sub-kanis build steps (emitting snapshots)
    # but never emit a graph_plan event.
    if isinstance(steps, list) and isinstance(root, str) and steps:
        typed_steps: list[JSONObject] = [s for s in steps if isinstance(s, dict)]
        if typed_steps:
            plan = _steps_to_plan(typed_steps, root, snapshot)
            if plan:
                updates["plan"] = plan


def _project_graph_plan(updates: dict[str, object], data: JSONObject) -> None:
    plan_val = data.get("plan")
    if isinstance(plan_val, dict):
        updates["plan"] = plan_val
        updates["step_count"] = _count_plan_nodes(plan_val)
    name = data.get("name")
    if isinstance(name, str) and name:
        updates["name"] = name
    rt = data.get("recordType")
    if isinstance(rt, str) and rt:
        updates["record_type"] = rt


def _project_model_selected(updates: dict[str, object], data: JSONObject) -> None:
    model_id = data.get("modelId")
    if isinstance(model_id, str):
        updates["model_id"] = model_id


def _project_graph_cleared(updates: dict[str, object]) -> None:
    from shared_py.defaults import DEFAULT_STREAM_NAME

    updates["name"] = DEFAULT_STREAM_NAME
    updates["plan"] = {}
    updates["steps"] = []
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
    if event_type == "strategy_link":
        wdk_id = event_data.get("wdkStrategyId")
        if isinstance(wdk_id, int):
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
            wdk_id = cast(int, updates["wdk_strategy_id"])
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
        "tool_calls",
        "citations",
        "planning_artifacts",
        "reasoning",
        "model_id",
        "subkani_calls",
        "subkani_status",
        "subkani_models",
        "subkani_token_usage",
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

    def build_assistant_message(
        self,
        data: JSONObject,
        entry_id: bytes | str,
    ) -> JSONObject:
        """Build a complete assistant message with accumulated metadata."""
        msg: JSONObject = {
            "role": "assistant",
            "content": data.get("content", ""),
            "messageId": data.get("messageId"),
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
            activity: JSONObject = {
                "calls": {k: list(v) for k, v in self.subkani_calls.items()},
                "status": dict(self.subkani_status),
            }
            if self.subkani_models:
                activity["models"] = dict(self.subkani_models)
            if self.subkani_token_usage:
                activity["tokenUsage"] = dict(self.subkani_token_usage)
            msg["subKaniActivity"] = activity
        # Preserve any fields directly on the event data.
        for key in ("citations", "planningArtifacts", "toolCalls", "reasoning"):
            if key in data and key not in msg:
                msg[key] = data[key]
        return msg


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

        match event_type:
            case "message_start":
                turn.reset()

            case "user_message":
                messages.append(
                    {
                        "role": "user",
                        "content": data.get("content", ""),
                        "messageId": data.get("messageId"),
                        "timestamp": _entry_id_to_iso(entry_id),
                    }
                )

            case "tool_call_start":
                turn.tool_calls.append(
                    {
                        "id": data.get("id", ""),
                        "name": data.get("name", ""),
                        "arguments": _parse_arguments(data.get("arguments")),
                    }
                )

            case "tool_call_end":
                call_id = data.get("id", "")
                for tc in turn.tool_calls:
                    if tc["id"] == call_id:
                        tc["result"] = data.get("result")
                        break

            case "citations":
                cites = data.get("citations")
                if isinstance(cites, list):
                    turn.citations.extend(cites)

            case "planning_artifact":
                artifact = data.get("planningArtifact")
                if artifact:
                    turn.planning_artifacts.append(artifact)

            case "reasoning":
                r = data.get("reasoning")
                if isinstance(r, str):
                    turn.reasoning = r

            case "model_selected":
                mid = data.get("modelId")
                if isinstance(mid, str):
                    turn.model_id = mid

            case "subkani_task_start":
                task = data.get("task", "")
                if task:
                    turn.subkani_status[task] = "running"
                    turn.subkani_calls.setdefault(task, [])
                    mid = data.get("modelId")
                    if isinstance(mid, str) and mid:
                        turn.subkani_models[task] = mid

            case "subkani_tool_call_start":
                task = data.get("task", "")
                if task:
                    turn.subkani_calls.setdefault(task, []).append(
                        {
                            "id": data.get("id", ""),
                            "name": data.get("name", ""),
                            "arguments": _parse_arguments(data.get("arguments")),
                        }
                    )

            case "subkani_tool_call_end":
                task = data.get("task", "")
                call_id = data.get("id", "")
                for tc in turn.subkani_calls.get(task, []):
                    if tc["id"] == call_id:
                        tc["result"] = data.get("result")
                        break

            case "subkani_task_end":
                task = data.get("task", "")
                if task:
                    turn.subkani_status[task] = data.get("status", "done")
                    mid = data.get("modelId")
                    if isinstance(mid, str) and mid:
                        turn.subkani_models[task] = mid
                    # Capture per-task token usage if present.
                    pt = data.get("promptTokens")
                    if pt is not None:
                        turn.subkani_token_usage[task] = {
                            "promptTokens": pt or 0,
                            "completionTokens": data.get("completionTokens", 0),
                            "llmCallCount": data.get("llmCallCount", 0),
                            "estimatedCostUsd": data.get("estimatedCostUsd", 0.0),
                        }

            case "assistant_message":
                messages.append(turn.build_assistant_message(data, entry_id))

            case "message_end":
                total = data.get("totalTokens", 0)
                if isinstance(total, int) and total > 0:
                    token_usage: JSONObject = {
                        "promptTokens": data.get("promptTokens", 0),
                        "completionTokens": data.get("completionTokens", 0),
                        "totalTokens": total,
                        "cachedTokens": data.get("cachedTokens", 0),
                        "toolCallCount": data.get("toolCallCount", 0),
                        "registeredToolCount": data.get("registeredToolCount", 0),
                        "llmCallCount": data.get("llmCallCount", 0),
                        "subKaniPromptTokens": data.get("subKaniPromptTokens", 0),
                        "subKaniCompletionTokens": data.get(
                            "subKaniCompletionTokens", 0
                        ),
                        "subKaniCallCount": data.get("subKaniCallCount", 0),
                        "estimatedCostUsd": data.get("estimatedCostUsd", 0.0),
                        "modelId": data.get("modelId", ""),
                    }
                    for i in range(len(messages) - 1, -1, -1):
                        if (
                            messages[i]["role"] == "user"
                            and "tokenUsage" not in messages[i]
                        ):
                            messages[i]["tokenUsage"] = token_usage
                            break
                    for i in range(len(messages) - 1, -1, -1):
                        if (
                            messages[i]["role"] == "assistant"
                            and "tokenUsage" not in messages[i]
                        ):
                            messages[i]["tokenUsage"] = token_usage
                            break
                turn.reset()

    return messages


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

    # Collect in-progress tool calls
    open_tools: dict[str, JSONObject] = {}
    for _eid, fields in entries[last_start_idx:]:
        event_type = fields.get(b"type", b"").decode()
        if event_type == "tool_call_start":
            try:
                data = json.loads(fields[b"data"])
                call_id = data.get("id", "")
                open_tools[call_id] = data
            except json.JSONDecodeError, KeyError:
                pass
        elif event_type == "tool_call_end":
            try:
                data = json.loads(fields[b"data"])
                call_id = data.get("id", "")
                open_tools.pop(call_id, None)
            except json.JSONDecodeError, KeyError:
                pass

    if not open_tools:
        return None

    return {
        "toolCalls": list(open_tools.values()),
    }
