"""Utilities for coordinating sub-kani task execution."""

import json
from collections.abc import Awaitable, Callable

from kani import Kani
from kani.models import ChatRole

from veupath_chatbot.ai.orchestration.delegation import CompiledNode
from veupath_chatbot.ai.orchestration.results import NodeResult
from veupath_chatbot.platform.event_schemas import (
    SubKaniToolCallEndEventData,
    SubKaniToolCallStartEventData,
)
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
    if not message.tool_calls:
        return
    for tc in message.tool_calls:
        await emit_event(
            {
                "type": "subkani_tool_call_start",
                "data": SubKaniToolCallStartEventData(
                    task=task,
                    id=tc.id,
                    name=tc.function.name,
                    arguments=tc.function.kwargs,
                ).model_dump(by_alias=True, exclude_none=True),
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
) -> SubKaniRoundResult:
    """Run a sub-kani round and collect created steps + error strings.

    Also tracks token usage from the sub-kani's assistant messages.
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
                    "data": SubKaniToolCallEndEventData(
                        task=task,
                        id=message.tool_call_id or "",
                        result=message.text,
                    ).model_dump(by_alias=True, exclude_none=True),
                }
            )

    return result


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
    tasks_by_id: dict[str, CompiledNode],
    results_by_id: dict[str, NodeResult],
) -> str | None:
    """Format dependency context for a subtask prompt."""
    task_obj = tasks_by_id.get(task_id)
    if task_obj is None:
        return None
    deps = task_obj.depends_on
    if not deps:
        return None

    lines: list[str] = []
    structured_steps: JSONArray = []

    for dep_id in deps:
        dep_node = tasks_by_id.get(dep_id)
        dep_task = dep_node.task if dep_node else dep_id
        dep_instructions = dep_node.instructions if dep_node else ""
        dep_result = results_by_id.get(dep_id)

        dep_result_dict = (
            dep_result.model_dump(by_alias=True, exclude_none=True)
            if dep_result
            else None
        )
        dep_steps: list[str] = (
            _collect_dep_steps(as_json_object(dep_result_dict), structured_steps)
            if isinstance(dep_result_dict, dict)
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
        return context.strip() or None
    try:
        result = json.dumps(context, ensure_ascii=True, indent=2, sort_keys=True)
    except (TypeError, ValueError) as exc:
        logger.debug("Failed to serialize task context as JSON", error=str(exc))
        result = str(context).strip()
    return result or None
