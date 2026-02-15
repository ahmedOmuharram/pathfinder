"""Utilities for coordinating sub-kani task execution."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable

from kani import Kani
from kani.models import ChatRole

from veupath_chatbot.platform.parsing import parse_jsonish
from veupath_chatbot.platform.types import (
    JSONArray,
    JSONObject,
    JSONValue,
    as_json_array,
    as_json_object,
)


async def consume_subkani_round(
    *,
    sub_kani: Kani,
    emit_event: Callable[[JSONObject], Awaitable[None]],
    task: str,
    round_prompt: str,
) -> tuple[str | None, JSONArray, list[str]]:
    """Run a sub-kani round and collect created steps + error strings."""
    response_text: str | None = None
    created_steps: JSONArray = []
    errors: list[str] = []

    async for message in sub_kani.full_round(round_prompt):
        if message.role == ChatRole.ASSISTANT and message.tool_calls:
            for tc in message.tool_calls:
                await emit_event(
                    {
                        "type": "subkani_tool_call_start",
                        "data": {
                            "task": task,
                            "id": tc.id,
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                )

        if message.role == ChatRole.ASSISTANT and message.text:
            response_text = message.text

        if message.role == ChatRole.FUNCTION:
            parsed = parse_jsonish(message.content)
            if isinstance(parsed, dict) and parsed.get("stepId"):
                created_steps.append(parsed)
            if isinstance(parsed, dict) and parsed.get("ok") is False:
                errors.append(
                    str(parsed.get("message") or parsed.get("code") or "tool error")
                )
            if isinstance(parsed, dict) and parsed.get("error"):
                errors.append(str(parsed.get("error")))
            if isinstance(parsed, dict) and parsed.get("invalid"):
                errors.append("invalid parameters")

            await emit_event(
                {
                    "type": "subkani_tool_call_end",
                    "data": {
                        "task": task,
                        "id": message.tool_call_id,
                        "result": message.content,
                    },
                }
            )

    return response_text, created_steps, errors


def format_dependency_context(
    *,
    task_id: str,
    tasks_by_id: dict[str, JSONObject],
    results_by_id: dict[str, JSONObject],
) -> str | None:
    """Format dependency context for a subtask prompt."""
    task_obj = tasks_by_id.get(task_id)
    if not isinstance(task_obj, dict):
        return None
    task_dict = as_json_object(task_obj)
    deps_value = task_dict.get("depends_on")
    if not isinstance(deps_value, list):
        return None
    deps = as_json_array(deps_value)
    if not deps:
        return None

    lines: list[str] = []
    structured_steps: JSONArray = []

    for dep_id_value in deps:
        if not isinstance(dep_id_value, str):
            continue
        dep_id = dep_id_value
        dep_node_value = tasks_by_id.get(dep_id)
        if not isinstance(dep_node_value, dict):
            dep_node: JSONObject = {}
        else:
            dep_node = as_json_object(dep_node_value)
        dep_task_value = dep_node.get("task", dep_id)
        dep_task = str(dep_task_value) if dep_task_value is not None else dep_id
        dep_hint = dep_node.get("hint")
        dep_result_value = results_by_id.get(dep_id)
        dep_steps: list[str] = []

        if isinstance(dep_result_value, dict):
            dep_result = as_json_object(dep_result_value)
            steps_value = dep_result.get("steps")
            if isinstance(steps_value, list):
                steps = as_json_array(steps_value)
                for step_value in steps:
                    if not isinstance(step_value, dict):
                        continue
                    step = as_json_object(step_value)
                    step_id_value = step.get("stepId") or step.get("id")
                    step_id = str(step_id_value) if step_id_value is not None else None
                    name_value = (
                        step.get("displayName")
                        or step.get("display_name")
                        or step.get("searchName")
                        or step.get("transformName")
                    )
                    name = str(name_value) if name_value is not None else None
                    if step_id and name:
                        dep_steps.append(f"{step_id} ({name})")
                    elif step_id:
                        dep_steps.append(str(step_id))
                    if step_id:
                        structured_steps.append(step)

        hint_suffix = f" (hint: {dep_hint})" if dep_hint else ""
        if dep_steps:
            lines.append(
                f"- {dep_id}: {dep_task}{hint_suffix} → {', '.join(dep_steps)}"
            )
        else:
            lines.append(f"- {dep_id}: {dep_task}{hint_suffix} → no steps created")

    if structured_steps:
        lines.append("Dependency steps (JSON):")
        lines.append(json.dumps(structured_steps, ensure_ascii=True, indent=2))

    return "\n".join(lines) if lines else None


def format_task_context(context: JSONValue) -> str | None:
    """Format optional per-task context for a subtask prompt."""
    if context is None:
        return None
    if isinstance(context, str):
        txt = context.strip()
        return txt if txt else None
    try:
        # Render JSON deterministically for model consumption.
        return json.dumps(context, ensure_ascii=True, indent=2, sort_keys=True)
    except Exception:
        return str(context).strip() or None


def extract_primary_step_id(result: JSONObject | None) -> str | None:
    """Pick the subtree root from a subtask result.

    Prefers the ``subtreeRoot`` field (set by the tree-first contract
    enforcement in the orchestrator).  Falls back to the last created step
    ID for backward compatibility.
    """
    if not isinstance(result, dict):
        return None
    # Prefer the explicitly tracked subtree root.
    subtree_root = result.get("subtreeRoot")
    if isinstance(subtree_root, str) and subtree_root:
        return subtree_root
    # Fallback: last step in the created-steps list.
    steps = result.get("steps")
    if not isinstance(steps, list):
        return None
    for step in reversed(steps):
        if not isinstance(step, dict):
            continue
        step_id = step.get("stepId") or step.get("id")
        if step_id:
            return str(step_id)
    return None
