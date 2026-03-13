"""HTTP streaming helpers (SSE event generation) for chat."""

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator
from uuid import uuid4

from kani import Kani
from kani.models import ChatRole

from veupath_chatbot.platform.errors import ErrorCode
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.parsing import parse_jsonish
from veupath_chatbot.platform.pydantic_validation import (
    parse_pydantic_validation_error_text,
)
from veupath_chatbot.platform.tool_errors import tool_error
from veupath_chatbot.platform.types import JSONArray, JSONObject
from veupath_chatbot.services.chat.events import tool_result_to_events

logger = get_logger(__name__)


async def stream_chat(agent: Kani, message: str) -> AsyncIterator[JSONObject]:
    """Stream chat responses from the agent as SSE-friendly events.

    NOTE: Does NOT emit ``message_start`` — the orchestrator (_chat_producer)
    emits the rich ``message_start`` with strategy context before calling us.
    """
    queue: asyncio.Queue[JSONObject] = asyncio.Queue()
    agent.event_queue = queue

    async def _produce_events() -> None:
        try:
            saw_assistant_message = False
            total_prompt_tokens = 0
            total_completion_tokens = 0
            tool_call_count = 0
            registered_tool_count = len(getattr(agent, "functions", {}))

            async for stream in agent.full_round_stream(message):
                # Assistant messages stream tokens; function calls typically do not, but are still emitted
                # as StreamManager entries in full_round_stream.
                if stream.role == ChatRole.ASSISTANT:
                    message_id = str(uuid4())
                    streamed_any = False
                    async for token in stream:
                        if not token:
                            continue
                        streamed_any = True
                        saw_assistant_message = True
                        await queue.put(
                            {
                                "type": "assistant_delta",
                                "data": {"messageId": message_id, "delta": token},
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
                                "data": {
                                    "promptTokens": total_prompt_tokens,
                                    "registeredToolCount": registered_tool_count,
                                },
                            }
                        )
                    if completion.completion_tokens:
                        total_completion_tokens += completion.completion_tokens
                    # msg.content can be a list of parts (e.g. Gemini multipart);
                    # msg.text always returns a joined plain string.
                    final_text = msg.text or ""
                    if final_text:
                        saw_assistant_message = True
                        await queue.put(
                            {
                                "type": "assistant_message",
                                "data": {
                                    "messageId": message_id,
                                    "content": final_text,
                                },
                            }
                        )
                    elif streamed_any:
                        # We streamed tokens but final message content is empty (rare). Keep the streamed message.
                        await queue.put(
                            {
                                "type": "assistant_message",
                                "data": {"messageId": message_id, "content": ""},
                            }
                        )

                    if msg.tool_calls:
                        tool_call_count += len(msg.tool_calls)
                        for tc in msg.tool_calls:
                            await queue.put(
                                {
                                    "type": "tool_call_start",
                                    "data": {
                                        "id": tc.id,
                                        "name": tc.function.name,
                                        "arguments": tc.function.arguments,
                                    },
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
                            "data": {
                                "id": msg.tool_call_id,
                                "result": tool_result_text,
                            },
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
                        logger.error("Error parsing tool result", error=str(e))

            if not saw_assistant_message:
                await queue.put(
                    {
                        "type": "assistant_message",
                        "data": {
                            "messageId": str(uuid4()),
                            "content": "I processed your request.",
                        },
                    }
                )
        except Exception as e:  # pragma: no cover
            logger.error(
                "Stream error",
                exc_info=True,
                error=str(e),
                errorType=type(e).__name__,
            )
            await queue.put({"type": "error", "data": {"error": str(e)}})
        finally:
            await queue.put(
                {
                    "type": "message_end",
                    "data": {
                        "promptTokens": total_prompt_tokens,
                        "completionTokens": total_completion_tokens,
                        "totalTokens": total_prompt_tokens + total_completion_tokens,
                        "toolCallCount": tool_call_count,
                        "registeredToolCount": registered_tool_count,
                    },
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
                yield event
                continue

            # After receiving message_end, keep draining for a short grace period to
            # capture any late-emitted sub-kani events, then close the stream.
            try:
                event = await asyncio.wait_for(queue.get(), timeout=idle_grace_seconds)
            except TimeoutError:
                # If producer finished and nothing else is queued, we can end safely.
                if producer.done() and queue.empty():
                    break
                continue

            # Ignore duplicate message_end; yield anything else.
            if event.get("type") != "message_end":
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
