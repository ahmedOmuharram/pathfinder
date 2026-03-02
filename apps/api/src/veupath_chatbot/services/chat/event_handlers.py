"""Per-event-type handlers (message, tool_call, graph, etc.)."""

from __future__ import annotations

from veupath_chatbot.platform.types import JSONObject, JSONValue, as_json_object
from veupath_chatbot.services.strategies.serialization import (
    build_steps_data_from_graph_snapshot,
)

from .events import (
    GRAPH_CLEARED,
    GRAPH_DELETED,
    GRAPH_PLAN,
    GRAPH_SNAPSHOT,
    OPTIMIZATION_PROGRESS,
    PLAN_UPDATE,
    REASONING,
    STRATEGY_LINK,
    STRATEGY_META,
)
from .sse import sse_event
from .utils import parse_uuid, sanitize_markdown


def resolve_graph_id(raw_id: str | None | JSONValue) -> str | None:
    """Resolve graph ID, converting JSONValue to str if needed.

    :param raw_id: Raw ID (str, None, or JSON).

    """
    if raw_id is None:
        return None
    if isinstance(raw_id, str):
        return raw_id
    return str(raw_id)


async def handle_event(proc, event_type: str, event_data: JSONObject) -> str | None:
    """Process one semantic event; returns SSE line (or None if skipped)."""
    if event_type == "message_start":
        return None

    if event_type == "assistant_message":
        content_value = event_data.get("content", "") or ""
        content = str(content_value) if content_value is not None else ""
        content = sanitize_markdown(content)
        event_data["content"] = content
        if content:
            proc.assistant_messages.append(content)

    elif event_type == "citations":
        citations = event_data.get("citations")
        if isinstance(citations, list):
            for c in citations:
                if isinstance(c, dict):
                    proc.citations.append(c)

    elif event_type == "planning_artifact":
        artifact = event_data.get("planningArtifact")
        if isinstance(artifact, dict):
            proc.planning_artifacts.append(artifact)

    elif event_type == REASONING:
        reasoning = event_data.get("reasoning")
        if isinstance(reasoning, str) and reasoning.strip():
            proc.reasoning = reasoning

    elif event_type == OPTIMIZATION_PROGRESS:
        proc.optimization_progress = event_data

    elif event_type == PLAN_UPDATE:
        title = event_data.get("title")
        if isinstance(title, str) and title.strip():
            await proc.strategy_repo.update(
                strategy_id=proc.strategy.id,
                name=title,
                title=title,
            )

    elif event_type == GRAPH_SNAPSHOT:
        await _handle_graph_snapshot(proc, event_data)

    elif event_type == GRAPH_PLAN:
        _handle_graph_plan(proc, event_data)

    elif event_type == STRATEGY_META:
        await _handle_strategy_meta(proc, event_data)

    elif event_type == GRAPH_CLEARED:
        graph_id = resolve_graph_id(event_data.get("graphId"))
        graph_uuid = parse_uuid(graph_id)
        if graph_uuid:
            await proc.strategy_repo.update(
                strategy_id=graph_uuid,
                title="Draft Strategy",
                plan={},
                record_type=None,
                wdk_strategy_id=None,
            )

    elif event_type == GRAPH_DELETED:
        graph_id = resolve_graph_id(event_data.get("graphId"))
        graph_uuid = parse_uuid(graph_id)
        if graph_uuid:
            await proc.strategy_repo.update(
                strategy_id=graph_uuid,
                title=None,
                plan={},
                record_type=None,
                wdk_strategy_id=None,
                wdk_strategy_id_set=True,
            )

    elif event_type == "subkani_task_start":
        task_value = event_data.get("task")
        task = str(task_value) if isinstance(task_value, str) else None
        if task:
            proc.subkani_status[task] = "running"
            proc.subkani_calls.setdefault(task, [])
            proc.thinking_dirty = True
            await proc.maybe_flush_thinking()

    elif event_type == "subkani_tool_call_start":
        task_value = event_data.get("task")
        call_id_value = event_data.get("id")
        task = str(task_value) if isinstance(task_value, str) else None
        call_id = str(call_id_value) if isinstance(call_id_value, str) else None
        if task and call_id:
            call = {
                "id": call_id,
                "name": event_data.get("name"),
                "arguments": event_data.get("arguments"),
            }
            proc.subkani_calls.setdefault(task, []).append(call)
            proc.subkani_calls_by_id[call_id] = (task, call)
            proc.thinking_dirty = True
            await proc.maybe_flush_thinking()

    elif event_type == "subkani_tool_call_end":
        call_id_value = event_data.get("id")
        call_id = str(call_id_value) if isinstance(call_id_value, str) else None
        if call_id and call_id in proc.subkani_calls_by_id:
            _, call = proc.subkani_calls_by_id[call_id]
            call["result"] = event_data.get("result")
            proc.thinking_dirty = True
            await proc.maybe_flush_thinking()

    elif event_type == "subkani_task_end":
        task_value = event_data.get("task")
        task = str(task_value) if isinstance(task_value, str) else None
        if task:
            status_value = event_data.get("status")
            status = str(status_value) if isinstance(status_value, str) else "done"
            proc.subkani_status[task] = status
            proc.thinking_dirty = True
            await proc.maybe_flush_thinking()

    elif event_type == "tool_call_start":
        call_id_value = event_data.get("id")
        call_id = str(call_id_value) if isinstance(call_id_value, str) else None
        if call_id:
            proc.tool_calls_by_id[call_id] = {
                "id": call_id,
                "name": event_data.get("name"),
                "arguments": event_data.get("arguments"),
            }
            proc.thinking_dirty = True
            await proc.maybe_flush_thinking()

    elif event_type == "tool_call_end":
        call_id_value = event_data.get("id")
        call_id = str(call_id_value) if isinstance(call_id_value, str) else None
        if call_id and call_id in proc.tool_calls_by_id:
            proc.tool_calls_by_id[call_id]["result"] = event_data.get("result")
            proc.tool_calls.append(proc.tool_calls_by_id[call_id])
            proc.thinking_dirty = True
            await proc.maybe_flush_thinking()

    elif event_type == STRATEGY_LINK:
        event_data = await _handle_strategy_link(proc, event_data)

    return sse_event(event_type, event_data)


async def _handle_graph_snapshot(proc, event_data: JSONObject) -> None:
    snapshot_value = event_data.get("graphSnapshot")
    if isinstance(snapshot_value, dict):
        snapshot = as_json_object(snapshot_value)
        graph_id_value = snapshot.get("graphId")
        graph_id = resolve_graph_id(graph_id_value)
        if graph_id:
            snapshot["graphId"] = graph_id
            event_data["graphSnapshot"] = snapshot
            proc.latest_graph_snapshots[str(graph_id)] = snapshot
            # Persist immediately so model-added steps are never "unsaved".
            graph_uuid = parse_uuid(graph_id)
            if graph_uuid:
                steps_data = build_steps_data_from_graph_snapshot(snapshot)
                root_step_id_value = snapshot.get("rootStepId")
                root_step_id = (
                    str(root_step_id_value)
                    if isinstance(root_step_id_value, str)
                    else None
                )
                name_value = snapshot.get("name")
                graph_name_value = snapshot.get("graphName")
                name: str | None = None
                if isinstance(name_value, str):
                    name = name_value
                elif isinstance(graph_name_value, str):
                    name = graph_name_value
                record_type_value = snapshot.get("recordType")
                record_type = (
                    str(record_type_value)
                    if isinstance(record_type_value, str)
                    else None
                )
                updated = await proc.strategy_repo.update(
                    strategy_id=graph_uuid,
                    name=name,
                    title=name,
                    record_type=record_type,
                    steps=steps_data,
                    root_step_id=root_step_id,
                    root_step_id_set=True,
                )
                if not updated:
                    name_str = name or "Draft Strategy"
                    await proc.strategy_repo.create(
                        user_id=proc.user_id,
                        name=name_str,
                        title=name_str,
                        site_id=proc.site_id,
                        record_type=record_type,
                        plan={},
                        steps=steps_data,
                        root_step_id=root_step_id,
                        strategy_id=graph_uuid,
                    )


def _handle_graph_plan(proc, event_data: JSONObject) -> None:
    graph_id_value = event_data.get("graphId")
    graph_id = resolve_graph_id(graph_id_value)
    if graph_id:
        plan_value = event_data.get("plan")
        name_value = event_data.get("name")
        record_type_value = event_data.get("recordType")
        description_value = event_data.get("description")
        proc.latest_plans[str(graph_id)] = {
            "plan": plan_value,
            "name": name_value,
            "recordType": record_type_value,
            "description": description_value,
        }


async def _handle_strategy_meta(proc, event_data: JSONObject) -> None:
    graph_id_value = event_data.get("graphId")
    graph_id = resolve_graph_id(graph_id_value)
    graph_uuid = parse_uuid(graph_id) if graph_id else None
    if graph_uuid:
        meta_name_value = event_data.get("name")
        meta_graph_name_value = event_data.get("graphName")
        meta_name: str | None = None
        if isinstance(meta_name_value, str):
            meta_name = meta_name_value
        elif isinstance(meta_graph_name_value, str):
            meta_name = meta_graph_name_value
        record_type_value = event_data.get("recordType")
        record_type = (
            str(record_type_value) if isinstance(record_type_value, str) else None
        )
        await proc.strategy_repo.update(
            strategy_id=graph_uuid,
            name=meta_name,
            title=meta_name,
            record_type=record_type,
        )


async def _handle_strategy_link(proc, event_data: JSONObject) -> JSONObject:
    _graph_id = resolve_graph_id(event_data.get("graphId"))
    current_graph_id = str(proc.strategy.id)
    # In execute mode, stream events must bind to the active strategy.
    # This avoids creating duplicate local conversations when background
    # WDK sync runs before stream finalization commits.
    graph_uuid = proc.strategy.id
    event_data["graphId"] = current_graph_id
    proc.pending_strategy_link[current_graph_id] = event_data
    if graph_uuid:
        wdk_strategy_id_value = event_data.get("wdkStrategyId")
        wdk_strategy_id: int | None = None
        if wdk_strategy_id_value is not None:
            if isinstance(wdk_strategy_id_value, int):
                wdk_strategy_id = wdk_strategy_id_value
            elif isinstance(wdk_strategy_id_value, (str, float)):
                try:
                    wdk_strategy_id = int(wdk_strategy_id_value)
                except ValueError, TypeError:
                    wdk_strategy_id = None
        if wdk_strategy_id is not None:
            updated = await proc.strategy_repo.update(
                strategy_id=graph_uuid,
                wdk_strategy_id=wdk_strategy_id,
                wdk_strategy_id_set=True,
            )
            if updated:
                proc.strategy.wdk_strategy_id = wdk_strategy_id
                # Explicitly commit linkage mid-stream so other requests
                # (e.g. sidebar sync) see the binding and do not import
                # the same WDK strategy as a separate local conversation.
                await proc.strategy_repo.session.commit()
            event_data = {**event_data, "strategySnapshotId": str(graph_uuid)}
    return event_data
