"""Utilities for coordinating sub-kani task execution."""

import json
from collections.abc import Awaitable, Callable

from kani import Kani
from kani.models import ChatRole

from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.parsing import parse_jsonish
from veupath_chatbot.platform.types import (
    JSONArray,
    JSONObject,
    JSONValue,
    as_json_array,
    as_json_object,
)

logger = get_logger(__name__)


class SubKaniRoundResult:
    """Result of a sub-kani round, including token usage."""

    __slots__ = (
        "completion_tokens",
        "created_steps",
        "errors",
        "llm_call_count",
        "prompt_tokens",
        "response_text",
    )

    def __init__(self) -> None:
        self.response_text: str | None = None
        self.created_steps: JSONArray = []
        self.errors: list[str] = []
        self.prompt_tokens: int = 0
        self.completion_tokens: int = 0
        self.llm_call_count: int = 0


def _extract_token_usage(message: object, result: SubKaniRoundResult) -> None:
    """Extract token usage from a kani assistant message."""
    extra = getattr(message, "extra", {})
    if not isinstance(extra, dict):
        return
    oai_usage = extra.get("openai_usage")
    if not oai_usage or not isinstance(oai_usage, dict):
        return
    result.prompt_tokens += (
        oai_usage.get("prompt_tokens", 0) or oai_usage.get("input_tokens", 0) or 0
    )
    result.completion_tokens += (
        oai_usage.get("completion_tokens", 0) or oai_usage.get("output_tokens", 0) or 0
    )


async def _emit_tool_call_starts(
    message: object,
    task: str,
    emit_event: Callable[[JSONObject], Awaitable[None]],
) -> None:
    """Emit subkani_tool_call_start events for tool calls in message."""
    tool_calls = getattr(message, "tool_calls", None)
    if not tool_calls:
        return
    for tc in tool_calls:
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


def _process_function_result(
    parsed: JSONObject,
    result: SubKaniRoundResult,
) -> None:
    """Process a parsed function result for step creation and errors."""
    if parsed.get("stepId"):
        result.created_steps.append(parsed)
    if parsed.get("ok") is False:
        result.errors.append(
            str(parsed.get("message") or parsed.get("code") or "tool error")
        )
    if parsed.get("error"):
        result.errors.append(str(parsed.get("error")))
    if parsed.get("invalid"):
        result.errors.append("invalid parameters")


async def consume_subkani_round(
    *,
    sub_kani: Kani,
    emit_event: Callable[[JSONObject], Awaitable[None]],
    task: str,
    round_prompt: str,
) -> tuple[str | None, JSONArray, list[str]]:
    """Run a sub-kani round and collect created steps + error strings.

    Also tracks token usage from the sub-kani's assistant messages.
    Returns the accumulated result via module-level _last_round_result.
    """
    result = SubKaniRoundResult()

    async for message in sub_kani.full_round(round_prompt):
        if message.role == ChatRole.ASSISTANT:
            result.llm_call_count += 1
            _extract_token_usage(message, result)
            await _emit_tool_call_starts(message, task, emit_event)
            if message.text:
                result.response_text = message.text

        if message.role == ChatRole.FUNCTION:
            content_text = message.content if isinstance(message.content, str) else None
            parsed = parse_jsonish(content_text)
            if isinstance(parsed, dict):
                _process_function_result(parsed, result)
            await emit_event(
                {
                    "type": "subkani_tool_call_end",
                    "data": {
                        "task": task,
                        "id": message.tool_call_id,
                        "result": message.text,
                    },
                }
            )

    # Store the result for the orchestrator to read
    _last_round_results[task] = result
    return result.response_text, result.created_steps, result.errors


# Module-level storage for round results (keyed by task)
_last_round_results: dict[str, SubKaniRoundResult] = {}


def get_round_result(task: str) -> SubKaniRoundResult | None:
    """Get the last round result for a task (includes token usage)."""
    return _last_round_results.pop(task, None)


def _extract_step_info(
    step: JSONObject,
) -> tuple[str | None, str | None]:
    """Extract step ID and display name from a step dict."""
    step_id_value = step.get("stepId") or step.get("id")
    step_id = str(step_id_value) if step_id_value is not None else None
    name_value = (
        step.get("displayName")
        or step.get("display_name")
        or step.get("searchName")
        or step.get("transformName")
    )
    name = str(name_value) if name_value is not None else None
    return step_id, name


def _collect_dep_steps(
    dep_result: JSONObject,
    structured_steps: JSONArray,
) -> list[str]:
    """Collect step descriptions from a dependency result."""
    dep_steps: list[str] = []
    steps_value = dep_result.get("steps")
    if not isinstance(steps_value, list):
        return dep_steps
    steps = as_json_array(steps_value)
    for step_value in steps:
        if not isinstance(step_value, dict):
            continue
        step = as_json_object(step_value)
        step_id, name = _extract_step_info(step)
        if step_id and name:
            dep_steps.append(f"{step_id} ({name})")
        elif step_id:
            dep_steps.append(str(step_id))
        if step_id:
            structured_steps.append(step)
    return dep_steps


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
        dep_node: JSONObject = (
            as_json_object(dep_node_value) if isinstance(dep_node_value, dict) else {}
        )
        dep_task_value = dep_node.get("task", dep_id)
        dep_task = str(dep_task_value) if dep_task_value is not None else dep_id
        dep_instructions = dep_node.get("instructions")
        dep_result_value = results_by_id.get(dep_id)

        dep_steps: list[str] = (
            _collect_dep_steps(as_json_object(dep_result_value), structured_steps)
            if isinstance(dep_result_value, dict)
            else []
        )

        instructions_suffix = (
            f" (instructions: {dep_instructions})" if dep_instructions else ""
        )
        steps_desc = ", ".join(dep_steps) if dep_steps else "no steps created"
        lines.append(f"- {dep_id}: {dep_task}{instructions_suffix} -> {steps_desc}")

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
        return txt or None
    try:
        return json.dumps(context, ensure_ascii=True, indent=2, sort_keys=True)
    except (TypeError, ValueError) as exc:
        logger.debug("Failed to serialize task context as JSON", error=str(exc))
        return str(context).strip() or None


def extract_primary_step_id(result: JSONObject | None) -> str | None:
    """Pick the subtree root from a subtask result.

    Prefers the ``subtreeRoot`` field (set by the tree-first contract
    enforcement in the orchestrator).  Falls back to the last created step
    ID when subtreeRoot is not set (e.g. combine results).
    """
    if not isinstance(result, dict):
        return None
    subtree_root = result.get("subtreeRoot")
    if isinstance(subtree_root, str) and subtree_root:
        return subtree_root
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
