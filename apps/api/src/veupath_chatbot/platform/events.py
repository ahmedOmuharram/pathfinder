"""Event sourcing core: emit events to Redis + project to PostgreSQL."""

import json
from datetime import UTC, datetime

from redis.asyncio import Redis
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from veupath_chatbot.persistence.models import StreamProjection
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject

logger = get_logger(__name__)


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

    return entry_id


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

    match event_type:
        case "strategy_meta":
            name = event_data.get("name")
            if isinstance(name, str) and name:
                updates["name"] = name
            rt = event_data.get("recordType")
            if isinstance(rt, str) and rt:
                updates["record_type"] = rt
        case "strategy_link":
            wdk_id = event_data.get("wdkStrategyId")
            if isinstance(wdk_id, int):
                updates["wdk_strategy_id"] = wdk_id
            is_saved = event_data.get("isSaved")
            if isinstance(is_saved, bool):
                updates["is_saved"] = is_saved
        case "graph_snapshot":
            snapshot = event_data.get("graphSnapshot")
            if isinstance(snapshot, dict):
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
        case "graph_plan":
            plan = event_data.get("plan")
            if isinstance(plan, dict):
                updates["plan"] = plan
                updates["step_count"] = _count_plan_nodes(plan)
            name = event_data.get("name")
            if isinstance(name, str) and name:
                updates["name"] = name
            rt = event_data.get("recordType")
            if isinstance(rt, str) and rt:
                updates["record_type"] = rt
        case "user_message" | "assistant_message":
            updates["message_count"] = StreamProjection.__table__.c.message_count + 1
        case "model_selected":
            model_id = event_data.get("modelId")
            if isinstance(model_id, str):
                updates["model_id"] = model_id
        case "graph_cleared":
            from shared_py.defaults import DEFAULT_STREAM_NAME

            updates["name"] = DEFAULT_STREAM_NAME
            updates["plan"] = {}
            updates["steps"] = []
            updates["root_step_id"] = None
            updates["step_count"] = 0
            updates["wdk_strategy_id"] = None
            updates["is_saved"] = False

    stmt = (
        update(StreamProjection)
        .where(StreamProjection.stream_id == stream_id)
        .values(**updates)
    )
    await session.execute(stmt)
    await session.flush()


def _entry_id_to_iso(entry_id: bytes | str) -> str:
    """Convert a Redis stream entry ID (e.g. '1709234567890-0') to ISO 8601."""
    raw = entry_id.decode() if isinstance(entry_id, bytes) else str(entry_id)
    ms_str = raw.split("-")[0]
    try:
        ts = datetime.fromtimestamp(int(ms_str) / 1000, tz=UTC)
    except ValueError, OSError:
        ts = datetime.now(UTC)
    return ts.isoformat()


async def read_stream_messages(redis: Redis, stream_id: str) -> list[JSONObject]:
    """Read all user + assistant messages from a Redis stream.

    Aggregates metadata from surrounding events (tool_call_start/end,
    citations, planning_artifact, reasoning, subkani events) into each
    assistant_message so the full conversation context survives refresh.

    Used by the GET /strategies/{id} endpoint to return chat history.
    """
    entries = await redis.xrange(f"stream:{stream_id}")
    messages: list[JSONObject] = []

    # Per-turn accumulators — reset on message_start / message_end.
    turn_tool_calls: list[JSONObject] = []
    turn_citations: list[JSONObject] = []
    turn_planning_artifacts: list[JSONObject] = []
    turn_reasoning: str | None = None
    turn_subkani_calls: dict[str, list[JSONObject]] = {}
    turn_subkani_status: dict[str, str] = {}

    def _reset_turn() -> None:
        nonlocal turn_reasoning
        turn_tool_calls.clear()
        turn_citations.clear()
        turn_planning_artifacts.clear()
        turn_reasoning = None
        turn_subkani_calls.clear()
        turn_subkani_status.clear()

    for entry_id, fields in entries:
        event_type = fields.get(b"type", b"").decode()
        try:
            data = json.loads(fields[b"data"])
        except json.JSONDecodeError, KeyError:
            continue

        match event_type:
            case "message_start":
                _reset_turn()

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
                turn_tool_calls.append(
                    {
                        "id": data.get("id", ""),
                        "name": data.get("name", ""),
                        "arguments": _parse_arguments(data.get("arguments")),
                    }
                )

            case "tool_call_end":
                call_id = data.get("id", "")
                for tc in turn_tool_calls:
                    if tc["id"] == call_id:
                        tc["result"] = data.get("result")
                        break

            case "citations":
                cites = data.get("citations")
                if isinstance(cites, list):
                    turn_citations.extend(cites)

            case "planning_artifact":
                artifact = data.get("planningArtifact")
                if artifact:
                    turn_planning_artifacts.append(artifact)

            case "reasoning":
                r = data.get("reasoning")
                if isinstance(r, str):
                    turn_reasoning = r

            case "subkani_task_start":
                task = data.get("task", "")
                if task:
                    turn_subkani_status[task] = "running"
                    turn_subkani_calls.setdefault(task, [])

            case "subkani_tool_call_start":
                task = data.get("task", "")
                if task:
                    turn_subkani_calls.setdefault(task, []).append(
                        {
                            "id": data.get("id", ""),
                            "name": data.get("name", ""),
                            "arguments": _parse_arguments(data.get("arguments")),
                        }
                    )

            case "subkani_tool_call_end":
                task = data.get("task", "")
                call_id = data.get("id", "")
                for tc in turn_subkani_calls.get(task, []):
                    if tc["id"] == call_id:
                        tc["result"] = data.get("result")
                        break

            case "subkani_task_end":
                task = data.get("task", "")
                if task:
                    turn_subkani_status[task] = data.get("status", "done")

            case "assistant_message":
                msg: JSONObject = {
                    "role": "assistant",
                    "content": data.get("content", ""),
                    "messageId": data.get("messageId"),
                    "timestamp": _entry_id_to_iso(entry_id),
                }
                if turn_tool_calls:
                    msg["toolCalls"] = list(turn_tool_calls)
                if turn_citations:
                    msg["citations"] = list(turn_citations)
                if turn_planning_artifacts:
                    msg["planningArtifacts"] = list(turn_planning_artifacts)
                if turn_reasoning:
                    msg["reasoning"] = turn_reasoning
                if turn_subkani_calls:
                    calls: JSONObject = {
                        k: list(v) for k, v in turn_subkani_calls.items()
                    }
                    status: JSONObject = dict(turn_subkani_status)
                    msg["subKaniActivity"] = {
                        "calls": calls,
                        "status": status,
                    }
                # Also preserve any fields that may be directly on the event data.
                for key in ("citations", "planningArtifacts", "toolCalls", "reasoning"):
                    if key in data and key not in msg:
                        msg[key] = data[key]
                messages.append(msg)

            case "message_end":
                total = data.get("totalTokens", 0)
                if isinstance(total, int) and total > 0:
                    token_usage: JSONObject = {
                        "promptTokens": data.get("promptTokens", 0),
                        "completionTokens": data.get("completionTokens", 0),
                        "totalTokens": total,
                        "toolCallCount": data.get("toolCallCount", 0),
                        "registeredToolCount": data.get("registeredToolCount", 0),
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
                _reset_turn()

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
