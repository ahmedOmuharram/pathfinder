"""Thinking payload + tool/subkani activity normalization."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from veupath_chatbot.platform.parsing import parse_jsonish

def normalize_tool_calls(raw_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for call in raw_calls:
        if not isinstance(call, dict):
            continue
        name = call.get("name")
        arguments = call.get("arguments")
        if not name or arguments is None:
            continue
        if isinstance(arguments, str):
            arguments = parse_jsonish(arguments)
        if not isinstance(arguments, dict):
            arguments = {}
        normalized.append(
            {
                "id": call.get("id") or "",
                "name": name,
                "arguments": arguments,
                "result": call.get("result"),
            }
        )
    return normalized


def normalize_subkani_activity(
    calls: dict[str, list[dict[str, Any]]],
    status: dict[str, str],
) -> dict[str, Any] | None:
    if not calls:
        return None
    normalized_calls: dict[str, list[dict[str, Any]]] = {}
    for task, task_calls in calls.items():
        normalized_calls[task] = normalize_tool_calls(task_calls)
    return {"calls": normalized_calls, "status": status}


def build_thinking_payload(
    tool_calls_by_id: dict[str, dict[str, Any]],
    subkani_calls: dict[str, list[dict[str, Any]]],
    subkani_status: dict[str, str],
) -> dict[str, Any]:
    normalized_tool_calls = normalize_tool_calls(list(tool_calls_by_id.values()))
    normalized_subkani = normalize_subkani_activity(subkani_calls, subkani_status)
    return {
        "toolCalls": normalized_tool_calls,
        "subKaniCalls": (normalized_subkani or {}).get("calls", {}),
        "subKaniStatus": (normalized_subkani or {}).get("status", {}),
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }

