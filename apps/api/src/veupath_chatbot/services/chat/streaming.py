"""HTTP streaming helpers (SSE event generation) for chat."""

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from uuid import uuid4

from kani import Kani
from kani.models import ChatRole
from kani.parts.reasoning import ReasoningPart

from veupath_chatbot.ai.models.pricing import estimate_cost
from veupath_chatbot.platform.errors import ErrorCode
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.parsing import parse_jsonish
from veupath_chatbot.platform.pydantic_validation import (
    parse_pydantic_validation_error_text,
)
from veupath_chatbot.platform.tool_errors import tool_error
from veupath_chatbot.platform.types import JSONArray, JSONObject
from veupath_chatbot.services.chat.events import tool_result_to_events
from veupath_chatbot.transport.http.schemas.sse import (
    AssistantDeltaEventData,
    AssistantMessageEventData,
    ErrorEventData,
    MessageEndEventData,
    ReasoningEventData,
    TokenUsagePartialEventData,
    ToolCallEndEventData,
    ToolCallStartEventData,
)

logger = get_logger(__name__)


def _cached_tokens_openai(extra: dict[str, object]) -> int:
    """Extract cached tokens from OpenAI usage (Chat Completions or Responses API)."""
    oai_usage = extra.get("openai_usage")
    if not oai_usage or not isinstance(oai_usage, dict):
        return 0
    for key in ("input_tokens_details", "prompt_tokens_details"):
        details = oai_usage.get(key)
        ct = details.get("cached_tokens") if isinstance(details, dict) else None
        if ct:
            return int(ct)
    return 0


def _cached_tokens_anthropic(extra: dict[str, object]) -> int:
    """Extract cached tokens from Anthropic usage."""
    anthropic_msg = extra.get("anthropic_message")
    if not anthropic_msg:
        return 0
    try:
        cache_read = anthropic_msg.usage.cache_read_input_tokens
        return int(cache_read) if cache_read else 0
    except AttributeError, TypeError:
        return 0


def _cached_tokens_google(extra: dict[str, object]) -> int:
    """Extract cached tokens from Google Gemini usage."""
    for key in ("google_response", "raw_response"):
        google_resp = extra.get(key)
        if not google_resp:
            continue
        try:
            ct = google_resp.usage_metadata.cached_content_token_count
            if ct:
                return int(ct)
        except AttributeError, TypeError:
            pass
    return 0


def _extract_cached_tokens(msg: object) -> int:
    """Extract cached token count from provider-specific usage stored in msg.extra.

    Kani engines store raw provider usage in the message's extra dict:
    - OpenAI Chat Completions: extra["openai_usage"].prompt_tokens_details.cached_tokens
    - OpenAI Responses API:    extra["openai_usage"].input_tokens_details.cached_tokens
    - Anthropic:               extra["anthropic_message"].usage.cache_read_input_tokens
    - Google:                  extra[RAW_RESPONSE_EXTRA_KEY].usage_metadata.cached_content_token_count
    """
    extra = getattr(msg, "extra", None)
    if not extra or not isinstance(extra, dict):
        return 0
    return (
        _cached_tokens_openai(extra)
        or _cached_tokens_anthropic(extra)
        or _cached_tokens_google(extra)
    )


def _extract_reasoning(msg: object) -> str | None:
    """Extract reasoning/thinking content from message parts.

    Anthropic thinking blocks arrive as ``ReasoningPart`` (or its subclass
    ``AnthropicThinkingPart``) inside ``msg.parts``.  The ``content``
    attribute holds the thinking text; ``__str__`` returns ``""`` so it
    won't appear in ``msg.text``.
    """
    parts = getattr(msg, "parts", None)
    if not parts:
        return None
    reasoning_parts = [
        part.content
        for part in parts
        if isinstance(part, ReasoningPart) and part.content
    ]
    return "\n\n".join(reasoning_parts) if reasoning_parts else None


def _accumulate_subkani_metrics(
    metrics: dict[str, int | float], end_data: JSONObject
) -> None:
    """Add sub-kani token counts from a task_end event into running metrics."""
    pt = end_data.get("promptTokens", 0)
    ct = end_data.get("completionTokens", 0)
    lc = end_data.get("llmCallCount", 0)
    metrics["subkani_prompt"] += int(pt) if isinstance(pt, (int, float)) else 0
    metrics["subkani_completion"] += int(ct) if isinstance(ct, (int, float)) else 0
    metrics["subkani_calls"] += int(lc) if isinstance(lc, (int, float)) else 0


async def _handle_function_stream(
    stream: object,
    agent: Kani,
    queue: asyncio.Queue[JSONObject],
) -> None:
    """Process a ChatRole.FUNCTION stream entry and emit tool_call_end + derived events."""
    msg = await stream.message()
    tool_result_text = msg.text
    parsed = parse_jsonish(tool_result_text)

    # Normalize tool-argument validation errors into structured tool_error payloads.
    if parsed is None and isinstance(tool_result_text, str):
        pyd = parse_pydantic_validation_error_text(tool_result_text)
        if pyd is not None:
            payload = tool_error(
                ErrorCode.VALIDATION_ERROR,
                "Tool arguments failed validation.",
                toolCallId=getattr(msg, "tool_call_id", None),
                **pyd,
            )
            tool_result_text = json.dumps(payload)
            parsed = payload

    await queue.put(
        {
            "type": "tool_call_end",
            "data": ToolCallEndEventData(
                id=msg.tool_call_id or "",
                result=tool_result_text,
            ).model_dump(by_alias=True),
        }
    )

    try:
        result: JSONObject | JSONArray
        result = {} if parsed is None else parsed

        logger.info("Tool result parsed", result_type=type(result).__name__)

        if isinstance(result, dict):
            session = getattr(agent, "strategy_session", None)
            get_graph = session.get_graph if session else None
            for event in tool_result_to_events(result, get_graph=get_graph):
                await queue.put(event)
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


def _maybe_accumulate_subkani(
    event: JSONObject, metrics: dict[str, int | float]
) -> None:
    """If *event* is a subkani_task_end, accumulate its token counts into *metrics*."""
    if event.get("type") == "subkani_task_end":
        end_data = event.get("data", {})
        if isinstance(end_data, dict):
            _accumulate_subkani_metrics(metrics, end_data)


@dataclass
class _RoundCounters:
    """Mutable counters updated during a single full_round_stream pass."""

    saw_assistant_message: bool = False
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    tool_call_count: int = 0
    llm_call_count: int = 0
    cached_tokens: int = 0
    accumulated_text_parts: list[str] = field(default_factory=list)


async def _process_assistant_stream(
    stream: object,
    counters: _RoundCounters,
    queue: asyncio.Queue[JSONObject],
    message_id: str,
    registered_tool_count: int,
) -> None:
    """Process a single ASSISTANT stream entry, updating counters and enqueueing events."""
    counters.llm_call_count += 1
    async for token in stream:
        if not token:
            continue
        counters.saw_assistant_message = True
        await queue.put(
            {
                "type": "assistant_delta",
                "data": AssistantDeltaEventData(
                    messageId=message_id, delta=token
                ).model_dump(by_alias=True),
            }
        )

    msg = await stream.message()
    completion = await stream.completion()
    if completion.prompt_tokens:
        counters.total_prompt_tokens += completion.prompt_tokens
        await queue.put(
            {
                "type": "token_usage_partial",
                "data": TokenUsagePartialEventData(
                    promptTokens=counters.total_prompt_tokens,
                    registeredToolCount=registered_tool_count,
                ).model_dump(by_alias=True),
            }
        )
    if completion.completion_tokens:
        counters.total_completion_tokens += completion.completion_tokens
    counters.cached_tokens += _extract_cached_tokens(msg)
    reasoning_text = _extract_reasoning(msg)
    if reasoning_text:
        await queue.put(
            {
                "type": "reasoning",
                "data": ReasoningEventData(reasoning=reasoning_text).model_dump(
                    by_alias=True
                ),
            }
        )
    final_text = msg.text or ""
    if final_text:
        counters.saw_assistant_message = True
        counters.accumulated_text_parts.append(final_text)

    if msg.tool_calls:
        counters.tool_call_count += len(msg.tool_calls)
        for tc in msg.tool_calls:
            await queue.put(
                {
                    "type": "tool_call_start",
                    "data": ToolCallStartEventData(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=tc.function.arguments,
                    ).model_dump(by_alias=True),
                }
            )


async def _produce_chat_events(
    agent: Kani,
    user_message: str,
    queue: asyncio.Queue[JSONObject],
    model_id: str,
    metrics: dict[str, int | float],
) -> None:
    """Run a full agent round and enqueue SSE events for the consumer.

    This is the producer task spawned by :func:`stream_chat`. It runs
    the kani full_round_stream, emitting assistant deltas, tool calls,
    reasoning blocks, and a final assistant_message + message_end.
    """
    registered_tool_count = len(getattr(agent, "functions", {}))
    message_id = str(uuid4())
    counters = _RoundCounters()

    try:
        async for stream in agent.full_round_stream(user_message):
            if stream.role == ChatRole.ASSISTANT:
                await _process_assistant_stream(
                    stream, counters, queue, message_id, registered_tool_count
                )
            elif stream.role == ChatRole.FUNCTION:
                await _handle_function_stream(stream, agent, queue)

        full_text = "\n\n".join(counters.accumulated_text_parts)
        await queue.put(
            {
                "type": "assistant_message",
                "data": AssistantMessageEventData(
                    messageId=message_id,
                    content=full_text
                    or (
                        ""
                        if counters.saw_assistant_message
                        else "I processed your request."
                    ),
                ).model_dump(by_alias=True),
            }
        )
    except Exception as e:  # pragma: no cover
        logger.error(
            "Stream error",
            exc_info=True,
            error=str(e),
            errorType=type(e).__name__,
        )
        await queue.put(
            {
                "type": "error",
                "data": ErrorEventData(error=str(e)).model_dump(by_alias=True),
            }
        )
    finally:
        estimated_cost = estimate_cost(
            model_id,
            prompt_tokens=counters.total_prompt_tokens,
            completion_tokens=counters.total_completion_tokens,
            cached_tokens=counters.cached_tokens,
        )
        await queue.put(
            {
                "type": "message_end",
                "data": MessageEndEventData(
                    promptTokens=counters.total_prompt_tokens,
                    completionTokens=counters.total_completion_tokens,
                    totalTokens=counters.total_prompt_tokens
                    + counters.total_completion_tokens,
                    cachedTokens=counters.cached_tokens,
                    toolCallCount=counters.tool_call_count,
                    registeredToolCount=registered_tool_count,
                    llmCallCount=counters.llm_call_count,
                    subKaniPromptTokens=int(metrics["subkani_prompt"]),
                    subKaniCompletionTokens=int(metrics["subkani_completion"]),
                    subKaniCallCount=int(metrics["subkani_calls"]),
                    estimatedCostUsd=estimated_cost,
                    modelId=model_id,
                ).model_dump(by_alias=True),
            }
        )


async def _drain_grace_period(
    queue: asyncio.Queue[JSONObject],
    producer: asyncio.Task[None],
    metrics: dict[str, int | float],
    idle_grace_seconds: float,
) -> AsyncIterator[JSONObject]:
    """Drain the queue during the grace period after message_end is received.

    Yields non-message_end events. Returns when the producer is done and
    the queue is empty, or keeps waiting while the producer is still running.
    """
    while True:
        try:
            event = await asyncio.wait_for(queue.get(), timeout=idle_grace_seconds)
        except TimeoutError:
            if producer.done():
                while not queue.empty():
                    event = queue.get_nowait()
                    if event.get("type") != "message_end":
                        _maybe_accumulate_subkani(event, metrics)
                        yield event
                return
            continue

        if event.get("type") != "message_end":
            _maybe_accumulate_subkani(event, metrics)
            yield event


async def stream_chat(
    agent: Kani, message: str, *, model_id: str = ""
) -> AsyncIterator[JSONObject]:
    """Stream chat responses from the agent as SSE-friendly events.

    NOTE: Does NOT emit ``message_start`` — the orchestrator (_chat_producer)
    emits the rich ``message_start`` with strategy context before calling us.
    """
    queue: asyncio.Queue[JSONObject] = asyncio.Queue()
    agent.event_queue = queue

    metrics: dict[str, int | float] = {
        "subkani_prompt": 0,
        "subkani_completion": 0,
        "subkani_calls": 0,
    }

    producer = asyncio.create_task(
        _produce_chat_events(agent, message, queue, model_id, metrics)
    )
    try:
        pending_end: JSONObject | None = None
        idle_grace_seconds = 0.25

        while True:
            event = await queue.get()
            if event.get("type") == "message_end":
                pending_end = event
                async for extra in _drain_grace_period(
                    queue, producer, metrics, idle_grace_seconds
                ):
                    yield extra
                break
            _maybe_accumulate_subkani(event, metrics)
            yield event

        if pending_end is not None:
            yield pending_end
    finally:
        cancel_event = getattr(agent, "_cancel_event", None)
        if cancel_event is not None:
            cancel_event.set()
        producer.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await producer
