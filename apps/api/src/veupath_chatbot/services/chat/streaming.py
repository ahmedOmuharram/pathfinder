"""HTTP streaming helpers (SSE event generation) for chat."""

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator
from uuid import uuid4

from kani import Kani
from kani.models import ChatRole

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

    # --- OpenAI (both Chat Completions and Responses API) ---
    # oai_usage is a DottableDict (dict subclass where __getattr__ = __getitem__).
    # Use .get() instead of getattr() to avoid KeyError on missing keys.
    oai_usage = extra.get("openai_usage")
    if oai_usage and isinstance(oai_usage, dict):
        for key in ("input_tokens_details", "prompt_tokens_details"):
            details = oai_usage.get(key)
            if details is None:
                continue
            ct = details.get("cached_tokens") if isinstance(details, dict) else None
            if ct:
                return int(ct)

    # --- Anthropic ---
    anthropic_msg = extra.get("anthropic_message")
    if anthropic_msg:
        try:
            cache_read = anthropic_msg.usage.cache_read_input_tokens
            if cache_read:
                return int(cache_read)
        except AttributeError, TypeError:
            pass

    # --- Google Gemini ---
    for key in ("google_response", "raw_response"):
        google_resp = extra.get(key)
        if google_resp:
            try:
                ct = google_resp.usage_metadata.cached_content_token_count
                if ct:
                    return int(ct)
            except AttributeError, TypeError:
                pass

    return 0


def _extract_reasoning(msg: object) -> str | None:
    """Extract reasoning/thinking content from message parts.

    Anthropic thinking blocks arrive as ``ReasoningPart`` (or its subclass
    ``AnthropicThinkingPart``) inside ``msg.parts``.  The ``content``
    attribute holds the thinking text; ``__str__`` returns ``""`` so it
    won't appear in ``msg.text``.
    """
    from kani.parts.reasoning import ReasoningPart

    parts = getattr(msg, "parts", None)
    if not parts:
        return None
    reasoning_parts: list[str] = []
    for part in parts:
        if isinstance(part, ReasoningPart) and part.content:
            reasoning_parts.append(part.content)
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


async def stream_chat(
    agent: Kani, message: str, *, model_id: str = ""
) -> AsyncIterator[JSONObject]:
    """Stream chat responses from the agent as SSE-friendly events.

    NOTE: Does NOT emit ``message_start`` — the orchestrator (_chat_producer)
    emits the rich ``message_start`` with strategy context before calling us.
    """
    queue: asyncio.Queue[JSONObject] = asyncio.Queue()
    agent.event_queue = queue

    # Shared metrics for cross-scope accumulation
    metrics: dict[str, int | float] = {
        "subkani_prompt": 0,
        "subkani_completion": 0,
        "subkani_calls": 0,
    }

    async def _produce_events() -> None:
        saw_assistant_message = False
        total_prompt_tokens = 0
        total_completion_tokens = 0
        tool_call_count = 0
        registered_tool_count = len(getattr(agent, "functions", {}))
        llm_call_count = 0
        cached_tokens = 0

        # Single message ID for the entire round so the frontend treats
        # all assistant text + tool calls as one logical message.
        message_id = str(uuid4())
        accumulated_text_parts: list[str] = []

        try:
            async for stream in agent.full_round_stream(message):
                # Assistant messages stream tokens; function calls typically do not, but are still emitted
                # as StreamManager entries in full_round_stream.
                if stream.role == ChatRole.ASSISTANT:
                    llm_call_count += 1
                    async for token in stream:
                        if not token:
                            continue
                        saw_assistant_message = True
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
                        total_prompt_tokens += completion.prompt_tokens
                        # Emit prompt tokens early so the frontend can show
                        # user token usage immediately, even if the model fails later.
                        await queue.put(
                            {
                                "type": "token_usage_partial",
                                "data": TokenUsagePartialEventData(
                                    promptTokens=total_prompt_tokens,
                                    registeredToolCount=registered_tool_count,
                                ).model_dump(by_alias=True),
                            }
                        )
                    if completion.completion_tokens:
                        total_completion_tokens += completion.completion_tokens
                    # Extract cached token count from provider usage stored
                    # in msg.extra by Kani's engine implementations.
                    cached_tokens += _extract_cached_tokens(msg)
                    # Emit reasoning/thinking blocks (Anthropic extended thinking,
                    # GPT-OSS, etc.) as a separate event so the frontend can
                    # display them in a collapsible panel.
                    reasoning_text = _extract_reasoning(msg)
                    if reasoning_text:
                        await queue.put(
                            {
                                "type": "reasoning",
                                "data": ReasoningEventData(
                                    reasoning=reasoning_text,
                                ).model_dump(by_alias=True),
                            }
                        )
                    # msg.content can be a list of parts (e.g. Gemini multipart);
                    # msg.text always returns a joined plain string.
                    final_text = msg.text or ""
                    if final_text:
                        saw_assistant_message = True
                        accumulated_text_parts.append(final_text)

                    # Don't emit assistant_message here — defer to end of
                    # round so the frontend keeps one message open across
                    # text → tool_call → text cycles.

                    if msg.tool_calls:
                        tool_call_count += len(msg.tool_calls)
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

                elif stream.role == ChatRole.FUNCTION:
                    msg = await stream.message()
                    tool_result_text = msg.text
                    parsed = parse_jsonish(tool_result_text)

                    # Normalize tool-argument validation errors into structured tool_error payloads.
                    # This catches cases like missing/extra params that the tool framework surfaces
                    # as a plain Pydantic ValidationError string.
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

                        logger.info(
                            "Tool result parsed", result_type=type(result).__name__
                        )

                        # tool_result_to_events expects JSONObject, not JSONArray
                        if isinstance(result, dict):
                            session = getattr(agent, "strategy_session", None)
                            get_graph = session.get_graph if session else None
                            for event in tool_result_to_events(
                                result, get_graph=get_graph
                            ):
                                await queue.put(event)
                    except Exception as e:  # pragma: no cover
                        logger.error(
                            "Error parsing tool result", error=str(e), exc_info=True
                        )
                        await queue.put(
                            {
                                "type": "error",
                                "data": ErrorEventData(
                                    error=f"Failed to process tool result: {e}"
                                ).model_dump(by_alias=True),
                            }
                        )

            # Emit one assistant_message for the entire round so the
            # frontend finalizes a single chat bubble.
            full_text = "\n\n".join(accumulated_text_parts)
            await queue.put(
                {
                    "type": "assistant_message",
                    "data": AssistantMessageEventData(
                        messageId=message_id,
                        content=full_text
                        or (
                            "" if saw_assistant_message else "I processed your request."
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
                prompt_tokens=total_prompt_tokens,
                completion_tokens=total_completion_tokens,
                cached_tokens=cached_tokens,
            )
            await queue.put(
                {
                    "type": "message_end",
                    "data": MessageEndEventData(
                        promptTokens=total_prompt_tokens,
                        completionTokens=total_completion_tokens,
                        totalTokens=total_prompt_tokens + total_completion_tokens,
                        cachedTokens=cached_tokens,
                        toolCallCount=tool_call_count,
                        registeredToolCount=registered_tool_count,
                        llmCallCount=llm_call_count,
                        subKaniPromptTokens=int(metrics["subkani_prompt"]),
                        subKaniCompletionTokens=int(metrics["subkani_completion"]),
                        subKaniCallCount=int(metrics["subkani_calls"]),
                        estimatedCostUsd=estimated_cost,
                        modelId=model_id,
                    ).model_dump(by_alias=True),
                }
            )

    producer = asyncio.create_task(_produce_events())
    try:
        # Important: sub-kani events are emitted via the same queue. In rare cases,
        # `message_end` can be enqueued before late-arriving sub-kani status updates.
        # If we break immediately, the UI can show "running" forever. To prevent this,
        # we delay yielding `message_end` until the queue has been quiescent briefly.
        pending_end: JSONObject | None = None
        idle_grace_seconds = 0.25

        while True:
            if pending_end is None:
                event = await queue.get()
                if event.get("type") == "message_end":
                    pending_end = event
                    continue
                # Accumulate sub-kani token usage from task_end events
                if event.get("type") == "subkani_task_end":
                    end_data = event.get("data", {})
                    if isinstance(end_data, dict):
                        _accumulate_subkani_metrics(metrics, end_data)
                yield event
                continue

            # After receiving message_end, keep draining for a short grace period to
            # capture any late-emitted sub-kani events, then close the stream.
            try:
                event = await asyncio.wait_for(queue.get(), timeout=idle_grace_seconds)
            except TimeoutError:
                if producer.done():
                    # Producer is done — drain any remaining items without waiting.
                    while not queue.empty():
                        event = queue.get_nowait()
                        if event.get("type") != "message_end":
                            if event.get("type") == "subkani_task_end":
                                end_data = event.get("data", {})
                                if isinstance(end_data, dict):
                                    _accumulate_subkani_metrics(metrics, end_data)
                            yield event
                    break
                continue

            # Ignore duplicate message_end; yield anything else.
            if event.get("type") != "message_end":
                # Accumulate sub-kani token usage from late task_end events
                if event.get("type") == "subkani_task_end":
                    end_data = event.get("data", {})
                    if isinstance(end_data, dict):
                        _accumulate_subkani_metrics(metrics, end_data)
                yield event

        # Now emit the stored end event as the final item.
        if pending_end is not None:
            yield pending_end
    finally:
        # Signal any long-running tools (e.g. parameter optimisation) to stop.
        cancel_event = getattr(agent, "_cancel_event", None)
        if cancel_event is not None:
            cancel_event.set()
        # Cancel the producer so it doesn't keep running after client disconnect.
        producer.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await producer
