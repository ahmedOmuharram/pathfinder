"""Helpers for building SSE event data dicts used in processor tests."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def message_start_event(*, strategy_id: str | None = None) -> dict[str, Any]:
    data: dict[str, Any] = {}
    if strategy_id:
        data["strategyId"] = strategy_id
    return data


def assistant_delta_event(delta: str, *, message_id: str = "m1") -> dict[str, Any]:
    return {"messageId": message_id, "delta": delta}


def assistant_message_event(content: str, *, message_id: str = "m1") -> dict[str, Any]:
    return {"messageId": message_id, "content": content}


def tool_call_start_event(
    call_id: str, name: str, arguments: str = "{}"
) -> dict[str, Any]:
    return {"id": call_id, "name": name, "arguments": arguments}


def tool_call_end_event(call_id: str, result: str = "{}") -> dict[str, Any]:
    return {"id": call_id, "result": result}


def citations_event(citations: list[dict[str, Any]]) -> dict[str, Any]:
    return {"citations": citations}


def planning_artifact_event(
    artifact_id: str, title: str = "Artifact", summary: str = "summary"
) -> dict[str, Any]:
    return {
        "planningArtifact": {
            "id": artifact_id,
            "title": title,
            "summaryMarkdown": summary,
            "assumptions": [],
            "parameters": {},
            "createdAt": datetime.now(UTC).isoformat(),
        }
    }


def reasoning_event(reasoning: str) -> dict[str, Any]:
    return {"reasoning": reasoning}


def optimization_progress_event(
    opt_id: str = "opt-1",
    status: str = "running",
    current_trial: int = 1,
    total_trials: int = 10,
) -> dict[str, Any]:
    return {
        "optimizationId": opt_id,
        "status": status,
        "currentTrial": current_trial,
        "totalTrials": total_trials,
    }


def graph_snapshot_event(
    graph_id: str,
    name: str = "Draft",
    steps: list | None = None,
    record_type: str | None = None,
) -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "graphId": graph_id,
        "name": name,
        "steps": steps or [],
    }
    if record_type:
        snapshot["recordType"] = record_type
    return {"graphSnapshot": snapshot}


def graph_plan_event(
    graph_id: str,
    plan: dict[str, Any] | None = None,
    name: str = "Plan",
    record_type: str | None = None,
) -> dict[str, Any]:
    return {
        "graphId": graph_id,
        "plan": plan or {},
        "name": name,
        "recordType": record_type,
    }


def strategy_link_event(
    graph_id: str,
    wdk_strategy_id: int | None = None,
    name: str | None = None,
    wdk_url: str | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {"graphId": graph_id}
    if wdk_strategy_id is not None:
        data["wdkStrategyId"] = wdk_strategy_id
    if name:
        data["name"] = name
    if wdk_url:
        data["wdkUrl"] = wdk_url
    return data


def strategy_meta_event(
    graph_id: str,
    name: str | None = None,
    record_type: str | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {"graphId": graph_id}
    if name:
        data["name"] = name
    if record_type:
        data["recordType"] = record_type
    return data


def graph_cleared_event(graph_id: str) -> dict[str, Any]:
    return {"graphId": graph_id}


def subkani_task_start_event(task: str) -> dict[str, Any]:
    return {"task": task}


def subkani_tool_call_start_event(
    task: str, call_id: str, name: str, arguments: str = "{}"
) -> dict[str, Any]:
    return {"task": task, "id": call_id, "name": name, "arguments": arguments}


def subkani_tool_call_end_event(
    task: str, call_id: str, result: str = "{}"
) -> dict[str, Any]:
    return {"task": task, "id": call_id, "result": result}


def subkani_task_end_event(task: str, status: str = "done") -> dict[str, Any]:
    return {"task": task, "status": status}


def plan_update_event(title: str) -> dict[str, Any]:
    return {"title": title}
