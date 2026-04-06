"""SSE event construction and emission helpers.

Pure event building — no pydantic-ai node iteration, no agent logic.
Every function here constructs or enqueues a typed SSE event dict.
"""

import asyncio
import json
from typing import cast

from pydantic import BaseModel
from pydantic_ai import FunctionToolResultEvent
from pydantic_ai.messages import ToolCallPart, ToolReturnPart

from veupath_chatbot.ai.orchestration.deps import AgentDeps
from veupath_chatbot.platform.errors import ErrorCode
from veupath_chatbot.platform.event_schemas import (
    AssistantDeltaEventData,
    ErrorEventData,
    ReasoningEventData,
    ToolCallEndEventData,
    ToolCallStartEventData,
)
from veupath_chatbot.platform.event_schemas_pipeline import (
    PhaseChangeEventData,
    PlanningThoughtEventData,
)
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.parsing import parse_jsonish
from veupath_chatbot.platform.pydantic_validation import (
    parse_pydantic_validation_error_text,
)
from veupath_chatbot.platform.tool_errors import tool_error
from veupath_chatbot.platform.types import JSONArray, JSONObject
from veupath_chatbot.services.chat.events import tool_result_to_events

logger = get_logger(__name__)


async def emit_delta(
    queue: asyncio.Queue[JSONObject], message_id: str, text: str
) -> None:
    """Emit an assistant_delta event."""
    await queue.put(
        {
            "type": "assistant_delta",
            "data": AssistantDeltaEventData(
                message_id=message_id, delta=text
            ).model_dump(by_alias=True),
        }
    )


async def emit_thoughts(
    queue: asyncio.Queue[JSONObject], thoughts: list[str]
) -> None:
    """Emit planning_thought events for completed thought blocks."""
    for thought in thoughts:
        await queue.put(
            {
                "type": "planning_thought",
                "data": PlanningThoughtEventData(thought=thought).model_dump(
                    by_alias=True
                ),
            }
        )


async def emit_reasoning(
    queue: asyncio.Queue[JSONObject], content: str,
) -> None:
    """Emit a reasoning event for thinking deltas."""
    await queue.put(
        {
            "type": "reasoning",
            "data": ReasoningEventData(
                reasoning=content
            ).model_dump(by_alias=True),
        }
    )


async def emit_phase_event(
    queue: asyncio.Queue[JSONObject], phase: str, status: str,
) -> None:
    """Emit a phase_change SSE event."""
    await queue.put({
        "type": "phase_change",
        "data": PhaseChangeEventData(
            phase=phase, status=status,
        ).model_dump(by_alias=True),
    })


def parse_tool_call_args(args: str | dict[str, object] | None) -> JSONObject:
    """Normalize ToolCallPart.args to a dict."""
    if isinstance(args, dict):
        return cast("JSONObject", args)
    if isinstance(args, str):
        try:
            parsed = json.loads(args)
        except (json.JSONDecodeError, ValueError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def tool_call_start_event(part: ToolCallPart) -> JSONObject:
    """Build a tool_call_start SSE event from a ToolCallPart."""
    return {
        "type": "tool_call_start",
        "data": ToolCallStartEventData(
            id=part.tool_call_id,
            name=part.tool_name,
            arguments=parse_tool_call_args(part.args),
        ).model_dump(by_alias=True),
    }


def serialize_tool_content(content: object) -> str:
    """Serialize tool result content to a JSON string.

    Handles str, dict, list, and Pydantic BaseModel instances.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        return json.dumps(content)
    if isinstance(content, list):
        return json.dumps(content)
    if isinstance(content, BaseModel):
        return json.dumps(content.model_dump(by_alias=True, mode="json"))
    return str(content)


async def emit_tool_end_and_semantics(
    tool_call_id: str,
    tool_result_text: str,
    queue: asyncio.Queue[JSONObject],
    deps: AgentDeps,
) -> None:
    """Emit tool_call_end and extract semantic events from a tool result."""
    parsed = parse_jsonish(tool_result_text)

    # Normalize pydantic validation errors into structured tool_error payloads.
    if parsed is None:
        pyd = parse_pydantic_validation_error_text(tool_result_text)
        if pyd is not None:
            payload = tool_error(
                ErrorCode.VALIDATION_ERROR,
                "Tool arguments failed validation.",
                toolCallId=tool_call_id,
                **pyd,
            )
            payload_dict = payload.model_dump(
                by_alias=True, exclude_none=True, mode="json"
            )
            tool_result_text = json.dumps(payload_dict)
            parsed = payload_dict

    await queue.put(
        {
            "type": "tool_call_end",
            "data": ToolCallEndEventData(
                id=tool_call_id,
                result=tool_result_text,
            ).model_dump(by_alias=True),
        }
    )

    # Extract semantic events from parsed tool result.
    try:
        result: JSONObject | JSONArray = {} if parsed is None else parsed
        if isinstance(result, dict):
            get_graph = deps.strategy_session.get_graph
            for semantic_event in tool_result_to_events(result, get_graph=get_graph):
                await queue.put(semantic_event)
    except Exception as e:  # pragma: no cover
        logger.error("Error parsing tool result", error=str(e), exc_info=True)
        await queue.put(
            {
                "type": "error",
                "data": ErrorEventData(
                    error=f"Failed to process tool result: {e}"
                ).model_dump(by_alias=True),
            }
        )


async def handle_tool_result(
    event: FunctionToolResultEvent,
    queue: asyncio.Queue[JSONObject],
    deps: AgentDeps,
) -> None:
    """Process a FunctionToolResultEvent and emit tool_call_end + semantic events."""
    result_part = event.result
    tool_call_id = result_part.tool_call_id
    if isinstance(result_part, ToolReturnPart):
        tool_result_text = serialize_tool_content(result_part.content)
    else:
        # RetryPromptPart — validation error from pydantic-ai
        tool_result_text = (
            result_part.content
            if isinstance(result_part.content, str)
            else str(result_part.content)
        )
    await emit_tool_end_and_semantics(tool_call_id, tool_result_text, queue, deps)
