"""Thinking payload + tool/subkani activity normalization."""

from __future__ import annotations

from datetime import UTC, datetime

from veupath_chatbot.platform.parsing import parse_jsonish
from veupath_chatbot.platform.types import JSONArray, JSONObject, JSONValue


def normalize_tool_calls(raw_calls: JSONArray) -> JSONArray:
    normalized: JSONArray = []
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
    calls: dict[str, JSONArray],
    status: dict[str, str],
) -> JSONObject | None:
    if not calls:
        return None
    normalized_calls: dict[str, JSONArray] = {}
    for task, task_calls in calls.items():
        normalized_calls[task] = normalize_tool_calls(task_calls)
    # Convert status dict values to JSONValue-compatible types
    status_json: dict[str, JSONValue] = dict(status.items())
    # Convert normalized_calls to JSONObject-compatible format
    calls_json: dict[str, JSONValue] = dict(normalized_calls.items())
    return {"calls": calls_json, "status": status_json}


def build_thinking_payload(
    tool_calls_by_id: dict[str, JSONObject],
    subkani_calls: dict[str, JSONArray],
    subkani_status: dict[str, str],
    *,
    reasoning: str | None = None,
) -> JSONObject:
    normalized_tool_calls = normalize_tool_calls(list(tool_calls_by_id.values()))
    normalized_subkani = normalize_subkani_activity(subkani_calls, subkani_status)
    payload: JSONObject = {
        "toolCalls": normalized_tool_calls,
        "subKaniCalls": (normalized_subkani or {}).get("calls", {}),
        "subKaniStatus": (normalized_subkani or {}).get("status", {}),
        "updatedAt": datetime.now(UTC).isoformat(),
    }
    if reasoning is not None:
        payload["reasoning"] = reasoning
    return payload
