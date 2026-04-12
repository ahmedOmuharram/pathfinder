"""Phase input/output and assistant-message helpers for streamed turns."""

import asyncio
import time

from pydantic_ai.messages import ModelMessage

from pathfinder.ai.orchestration.deps import AgentDeps
from pathfinder.ai.prompts.loader import PromptBundle, load_system_prompt_bundle
from pathfinder.platform.event_schemas import AssistantMessageEventData
from pathfinder.platform.types import JSONObject
from pathfinder.services.chat.streaming.node_streaming import TurnCounters
from pathfinder.services.chat.streaming.turn_payloads import phase_result_summary
from pathfinder.services.chat.streaming.turn_telemetry import TurnRuntimeTelemetry


def prompt_bundle_for_deps(deps: AgentDeps) -> PromptBundle:
    """Return the effective shared system-prompt bundle for this turn."""
    return load_system_prompt_bundle(include_site_hints=deps.context_summary is None)


def phase_input_payload(
    *,
    phase: str,
    phase_prompt: str,
    message_history: list[ModelMessage] | None,
    deps: AgentDeps,
) -> JSONObject:
    """Return a compact structured summary of what entered this phase."""
    payload: JSONObject = {
        "phase": phase,
        "messageHistoryCount": len(message_history or []),
        "hasContextSummary": deps.context_summary is not None,
        "hasProblemFrame": deps.problem_frame is not None,
        "hasApprovedPlan": deps.approved_plan is not None,
        "hasPlanAction": deps.plan_action is not None,
    }
    if phase_prompt:
        payload["prompt"] = phase_prompt
    return payload


def phase_output_payload(
    deps: AgentDeps,
    phase: str,
    *,
    counters: TurnCounters,
    tool_call_count_before: int,
    runtime: TurnRuntimeTelemetry,
) -> str | JSONObject | None:
    """Return the assistant/tool summary produced by the phase."""
    content = "\n\n".join(counters.accumulated_text_parts).strip()
    tool_calls_used = counters.tool_call_count - tool_call_count_before
    result_summary = phase_result_summary(deps, phase, runtime=runtime)
    if not content and tool_calls_used <= 0 and result_summary is None:
        return None
    payload: JSONObject = {}
    if content:
        payload["assistantMessage"] = content
    if tool_calls_used > 0:
        payload["toolCallsUsed"] = tool_calls_used
    if result_summary is not None:
        payload["result"] = result_summary.model_dump(by_alias=True)
    return payload


def reset_phase_message_buffer(counters: TurnCounters) -> None:
    """Clear the per-phase assistant text buffer while preserving token counters."""
    counters.saw_assistant_message = False
    counters.accumulated_text_parts.clear()


async def emit_phase_assistant_message(
    queue: asyncio.Queue[JSONObject],
    counters: TurnCounters,
    *,
    phase: str,
    message_id: str,
    message_group_id: str | None,
    tool_call_count_before: int,
) -> bool:
    """Emit the assistant message accumulated for one pipeline phase."""
    content = "\n\n".join(counters.accumulated_text_parts).strip()
    phase_had_tool_calls = counters.tool_call_count > tool_call_count_before
    if not content and not counters.saw_assistant_message and not phase_had_tool_calls:
        return False
    if content:
        counters.last_assistant_message = content
    if counters.first_assistant_message_at_monotonic is None:
        counters.first_assistant_message_at_monotonic = time.monotonic()

    await queue.put(
        {
            "type": "assistant_message",
            "data": AssistantMessageEventData(
                message_id=message_id,
                message_group_id=message_group_id,
                phase=phase,
                content=content,
            ).model_dump(by_alias=True),
        }
    )
    return True
