"""pydantic-ai node iteration — streams ModelRequestNode and CallToolsNode.

Consumes the ``Agent.iter()`` node stream, dispatching to event helpers
for deltas, reasoning, tool calls, and tool results.
"""

import asyncio

# ── Counters ──────────────────────────────────────────────────────────────
from dataclasses import dataclass, field

from pydantic_ai import (
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    PartDeltaEvent,
    PartStartEvent,
    TextPartDelta,
    ThinkingPartDelta,
)
from pydantic_ai.agent import AgentRun, CallToolsNode, ModelRequestNode
from pydantic_ai.messages import TextPart, ToolCallPart
from pydantic_ai.result import AgentStream
from pydantic_ai.usage import RunUsage

from veupath_chatbot.ai.orchestration.deps import AgentDeps
from veupath_chatbot.platform.event_schemas import TokenUsagePartialEventData
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.chat.streaming.events import (
    emit_delta,
    emit_reasoning,
    emit_thoughts,
    handle_tool_result,
    tool_call_start_event,
)
from veupath_chatbot.services.chat.streaming.tag_stripper import (
    PLAN_THINKING_RE,
    StreamingTagStripper,
)


@dataclass
class TurnCounters:
    """Mutable counters accumulated across all phases in a single turn."""

    saw_assistant_message: bool = False
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    tool_call_count: int = 0
    llm_call_count: int = 0
    accumulated_text_parts: list[str] = field(default_factory=list)


def merge_usage(counters: TurnCounters, usage: RunUsage) -> None:
    """Fold a pydantic-ai ``Usage`` into the running counters."""
    counters.input_tokens += usage.input_tokens or 0
    counters.output_tokens += usage.output_tokens or 0
    counters.cache_read_tokens += usage.cache_read_tokens or 0
    counters.llm_call_count += usage.requests or 0
    counters.tool_call_count += usage.tool_calls or 0


# ── Node-level handlers ──────────────────────────────────────────────────


async def handle_text_delta(
    event: PartDeltaEvent,
    stripper: StreamingTagStripper,
    queue: asyncio.Queue[JSONObject],
    message_id: str,
    counters: TurnCounters,
) -> None:
    """Handle a TextPartDelta within a model request stream."""
    delta = event.delta
    if not isinstance(delta, TextPartDelta):
        return
    clean_text, thoughts = stripper.feed(delta.content_delta)
    await emit_thoughts(queue, thoughts)
    if clean_text:
        counters.saw_assistant_message = True
        await emit_delta(queue, message_id, clean_text)


async def handle_thinking_delta(
    event: PartDeltaEvent,
    queue: asyncio.Queue[JSONObject],
) -> None:
    """Handle a ThinkingPartDelta within a model request stream."""
    delta = event.delta
    if not isinstance(delta, ThinkingPartDelta):
        return
    if delta.content_delta:
        await emit_reasoning(queue, delta.content_delta)


async def accumulate_final_text(
    stream: AgentStream[AgentDeps, str],
    counters: TurnCounters,
) -> None:
    """Extract final clean text from the completed stream response."""
    response = stream.response
    if not response or not response.parts:
        return
    text_parts = [p.content for p in response.parts if isinstance(p, TextPart)]
    if not text_parts:
        return
    full_text = "\n\n".join(text_parts)
    clean_text = PLAN_THINKING_RE.sub("", full_text).strip()
    if clean_text:
        counters.saw_assistant_message = True
        counters.accumulated_text_parts.append(clean_text)


# ── High-level node streaming ────────────────────────────────────────────


async def stream_model_request(
    node: ModelRequestNode[AgentDeps, str],
    run: AgentRun[AgentDeps, str],
    queue: asyncio.Queue[JSONObject],
    message_id: str,
    counters: TurnCounters,
) -> None:
    """Stream a ModelRequestNode, emitting deltas, reasoning, and tool_call_start events."""
    stripper = StreamingTagStripper()

    async with node.stream(run.ctx) as request_stream:
        stream: AgentStream[AgentDeps, str] = request_stream
        async for event in stream:
            if isinstance(event, PartDeltaEvent):
                if isinstance(event.delta, TextPartDelta):
                    await handle_text_delta(event, stripper, queue, message_id, counters)
                elif isinstance(event.delta, ThinkingPartDelta):
                    await handle_thinking_delta(event, queue)
            elif isinstance(event, PartStartEvent) and isinstance(
                event.part, ToolCallPart
            ):
                    # tool_call_start is emitted by stream_call_tools
                    # (via FunctionToolCallEvent) — skip here to avoid duplicates.
                    pass

        # Flush remaining buffered text from the tag stripper.
        remaining = stripper.flush()
        if remaining:
            counters.saw_assistant_message = True
            await emit_delta(queue, message_id, remaining)

        # Accumulate final text from the response.
        await accumulate_final_text(stream, counters)

        # Emit partial token usage.
        usage = stream.usage()
        if usage.input_tokens:
            await queue.put(
                {
                    "type": "token_usage_partial",
                    "data": TokenUsagePartialEventData(
                        prompt_tokens=counters.input_tokens + (usage.input_tokens or 0),
                        registered_tool_count=0,
                    ).model_dump(by_alias=True),
                }
            )


async def stream_call_tools(
    node: CallToolsNode[AgentDeps, str],
    run: AgentRun[AgentDeps, str],
    queue: asyncio.Queue[JSONObject],
    deps: AgentDeps,
) -> None:
    """Stream a CallToolsNode, emitting tool_call_start and tool_call_end events."""
    async with node.stream(run.ctx) as handle_stream:
        async for event in handle_stream:
            if isinstance(event, FunctionToolCallEvent):
                await queue.put(tool_call_start_event(event.part))
            elif isinstance(event, FunctionToolResultEvent):
                await handle_tool_result(event, queue, deps)
