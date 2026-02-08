"""Utilities for coordinating sub-kani task execution."""

from __future__ import annotations

import json
from typing import Any, Awaitable, Callable

from kani.models import ChatRole

from veupath_chatbot.platform.parsing import parse_jsonish


async def consume_subkani_round(
    *,
    sub_kani: Any,
    emit_event: Callable[[dict[str, Any]], Awaitable[None]],
    task: str,
    round_prompt: str,
) -> tuple[str | None, list[dict[str, Any]], list[str]]:
    """Run a sub-kani round and collect created steps + error strings."""
    response_text: str | None = None
    created_steps: list[dict[str, Any]] = []
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
    tasks_by_id: dict[str, dict[str, Any]],
    results_by_id: dict[str, dict[str, Any]],
) -> str | None:
    """Format dependency context for a subtask prompt."""
    deps = (tasks_by_id.get(task_id) or {}).get("depends_on") or []
    if not deps:
        return None

    lines: list[str] = []
    structured_steps: list[dict[str, Any]] = []

    for dep_id in deps:
        dep_node = tasks_by_id.get(dep_id) or {}
        dep_task = dep_node.get("task", dep_id)
        dep_hint = dep_node.get("hint")
        dep_result = results_by_id.get(dep_id)
        dep_steps: list[str] = []

        if isinstance(dep_result, dict):
            for step in dep_result.get("steps") or []:
                if not isinstance(step, dict):
                    continue
                step_id = step.get("stepId") or step.get("id")
                name = (
                    step.get("displayName")
                    or step.get("display_name")
                    or step.get("searchName")
                    or step.get("transformName")
                )
                if step_id and name:
                    dep_steps.append(f"{step_id} ({name})")
                elif step_id:
                    dep_steps.append(str(step_id))
                if step_id:
                    structured_steps.append(step)

        hint_suffix = f" (hint: {dep_hint})" if dep_hint else ""
        if dep_steps:
            lines.append(f"- {dep_id}: {dep_task}{hint_suffix} → {', '.join(dep_steps)}")
        else:
            lines.append(f"- {dep_id}: {dep_task}{hint_suffix} → no steps created")

    if structured_steps:
        lines.append("Dependency steps (JSON):")
        lines.append(json.dumps(structured_steps, ensure_ascii=True, indent=2))

    return "\n".join(lines) if lines else None


def format_task_context(context: Any) -> str | None:
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


def extract_primary_step_id(result: dict[str, Any] | None) -> str | None:
    """Pick the most relevant created step id from a subtask result."""
    if not isinstance(result, dict):
        return None
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

