"""HTTP streaming helpers (SSE event generation) for chat."""

from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator, TYPE_CHECKING

from kani.models import ChatRole

from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.parsing import parse_jsonish
from veupath_chatbot.services.chat.events import tool_result_to_events

if TYPE_CHECKING:  # pragma: no cover
    from veupath_chatbot.ai.agent_runtime import PathfinderAgent

logger = get_logger(__name__)


async def stream_chat(agent: "PathfinderAgent", message: str) -> AsyncIterator[dict]:
    """Stream chat responses from the agent as SSE-friendly events."""
    yield {"type": "message_start", "data": {}}

    queue: asyncio.Queue = asyncio.Queue()
    agent.event_queue = queue

    async def _produce_events():
        try:
            saw_assistant_message = False

            async for msg in agent.full_round(message):
                if msg.role == ChatRole.ASSISTANT:
                    if msg.content:
                        saw_assistant_message = True
                        await queue.put(
                            {"type": "assistant_message", "data": {"content": msg.content}}
                        )

                    if msg.tool_calls:
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

                elif msg.role == ChatRole.FUNCTION:
                    await queue.put(
                        {
                            "type": "tool_call_end",
                            "data": {"id": msg.tool_call_id, "result": msg.content},
                        }
                    )

                    try:
                        parsed = parse_jsonish(msg.content)
                        result: dict | list | Any
                        if parsed is None:
                            result = {}
                        else:
                            result = parsed

                        logger.info("Tool result parsed", result_type=type(result).__name__)

                        for event in tool_result_to_events(
                            result, get_graph=agent.strategy_session.get_graph
                        ):
                            await queue.put(event)
                    except Exception as e:  # pragma: no cover
                        logger.error("Error parsing tool result", error=str(e))

            if not saw_assistant_message:
                await queue.put(
                    {
                        "type": "assistant_message",
                        "data": {"content": "I processed your request."},
                    }
                )
        except Exception as e:  # pragma: no cover
            logger.error("Stream error", exc_info=True)
            await queue.put({"type": "error", "data": {"error": str(e)}})
        finally:
            await queue.put({"type": "message_end", "data": {}})

    producer = asyncio.create_task(_produce_events())
    try:
        while True:
            event = await queue.get()
            yield event
            if event.get("type") == "message_end":
                break
    finally:
        await producer

