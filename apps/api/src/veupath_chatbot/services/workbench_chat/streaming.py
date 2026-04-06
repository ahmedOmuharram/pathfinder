"""Workbench agent streaming — iterate pydantic-ai nodes and yield SSE events.

Handles ModelRequestNode (text deltas) and CallToolsNode (tool
start/end) events, accumulating token counters for the final
message_end envelope.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from uuid import uuid4

from pydantic_ai import Agent
from pydantic_ai.agent import AgentRun, CallToolsNode, ModelRequestNode
from pydantic_ai.messages import (
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    ModelMessage,
    PartDeltaEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.result import AgentStream
from pydantic_ai.usage import RunUsage

from veupath_chatbot.ai.models.pricing import estimate_cost
from veupath_chatbot.platform.event_schemas import (
    AssistantDeltaEventData,
    AssistantMessageEventData,
    MessageEndEventData,
    ToolCallEndEventData,
)
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.experiment.workbench_deps import WorkbenchDeps
from veupath_chatbot.services.workbench_chat.events import (
    serialize_tool_content,
    tool_call_start_event,
)


@dataclass
class TurnCounters:
    """Mutable counters accumulated across a single workbench turn."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    tool_call_count: int = 0
    llm_call_count: int = 0
    accumulated_text: str = ""


def merge_usage(counters: TurnCounters, usage: RunUsage) -> None:
    """Fold a pydantic-ai Usage into the running counters."""
    counters.input_tokens += usage.input_tokens or 0
    counters.output_tokens += usage.output_tokens or 0
    counters.cache_read_tokens += usage.cache_read_tokens or 0
    counters.llm_call_count += usage.requests or 0


async def stream_workbench_agent(
    agent: Agent[WorkbenchDeps, str],
    message: str,
    deps: WorkbenchDeps,
    history: list[ModelMessage],
    model_id: str,
    tool_count: int,
) -> AsyncIterator[JSONObject]:
    """Run the workbench agent and yield SSE-shaped event dicts."""
    message_id = str(uuid4())
    counters = TurnCounters()

    async with agent.iter(
        message,
        deps=deps,
        message_history=history,
    ) as run:
        async for node in run:
            if Agent.is_model_request_node(node):
                async for event in _stream_model_request(
                    node, run, message_id, counters
                ):
                    yield event
            elif Agent.is_call_tools_node(node):
                async for event in _stream_call_tools(node, run, counters):
                    yield event

        merge_usage(counters, run.usage())

    # Emit the final assistant_message event.
    yield {
        "type": "assistant_message",
        "data": AssistantMessageEventData(
            message_id=message_id,
            content=counters.accumulated_text or "I processed your request.",
        ).model_dump(by_alias=True),
    }

    # Emit message_end with usage stats.
    estimated_cost = estimate_cost(
        model_id,
        prompt_tokens=counters.input_tokens,
        completion_tokens=counters.output_tokens,
        cached_tokens=counters.cache_read_tokens,
    )
    yield {
        "type": "message_end",
        "data": MessageEndEventData(
            prompt_tokens=counters.input_tokens,
            completion_tokens=counters.output_tokens,
            total_tokens=counters.input_tokens + counters.output_tokens,
            cached_tokens=counters.cache_read_tokens,
            tool_call_count=counters.tool_call_count,
            registered_tool_count=tool_count,
            llm_call_count=counters.llm_call_count,
            estimated_cost_usd=estimated_cost,
            model_id=model_id,
        ).model_dump(by_alias=True),
    }


async def _stream_model_request(
    node: ModelRequestNode[WorkbenchDeps, str],
    run: AgentRun[WorkbenchDeps, str],
    message_id: str,
    counters: TurnCounters,
) -> AsyncIterator[JSONObject]:
    """Stream a ModelRequestNode, emitting text deltas and tool_call_start events."""
    async with node.stream(run.ctx) as request_stream:
        stream: AgentStream[WorkbenchDeps, str] = request_stream
        async for event in stream:
            if isinstance(event, PartDeltaEvent) and isinstance(
                event.delta, TextPartDelta
            ):
                text = event.delta.content_delta
                if text:
                    counters.accumulated_text += text
                    yield {
                        "type": "assistant_delta",
                        "data": AssistantDeltaEventData(
                            message_id=message_id, delta=text
                        ).model_dump(by_alias=True),
                    }
            elif isinstance(event, PartStartEvent) and isinstance(
                event.part, ToolCallPart
            ):
                # tool_call_start is emitted by _stream_call_tools
                # via FunctionToolCallEvent — skip here to avoid duplicates.
                pass

        # Accumulate final text from response parts.
        response = stream.response
        if response and response.parts:
            text_parts = [
                p.content for p in response.parts if isinstance(p, TextPart)
            ]
            if text_parts:
                counters.accumulated_text = "\n\n".join(text_parts)


async def _stream_call_tools(
    node: CallToolsNode[WorkbenchDeps, str],
    run: AgentRun[WorkbenchDeps, str],
    counters: TurnCounters | None = None,
) -> AsyncIterator[JSONObject]:
    """Stream a CallToolsNode, emitting tool_call_start and tool_call_end events."""
    async with node.stream(run.ctx) as handle_stream:
        async for event in handle_stream:
            if isinstance(event, FunctionToolCallEvent):
                yield tool_call_start_event(event.part)
                if counters is not None:
                    counters.tool_call_count += 1
            elif isinstance(event, FunctionToolResultEvent):
                result_part = event.result
                tool_call_id = result_part.tool_call_id
                if isinstance(result_part, ToolReturnPart):
                    tool_result_text = serialize_tool_content(result_part.content)
                else:
                    tool_result_text = (
                        result_part.content
                        if isinstance(result_part.content, str)
                        else str(result_part.content)
                    )

                yield {
                    "type": "tool_call_end",
                    "data": ToolCallEndEventData(
                        id=tool_call_id,
                        result=tool_result_text,
                    ).model_dump(by_alias=True),
                }
