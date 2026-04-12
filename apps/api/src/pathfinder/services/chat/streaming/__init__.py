"""HTTP streaming package (SSE event generation) for pydantic-ai agents.

Uses a queue-based producer/consumer pattern.  The producer runs the
pydantic-ai pipeline via ``Agent.iter()`` / ``node.stream()``, mapping
framework events to PathFinder's SSE event contract.
"""

import asyncio
import contextlib
from collections.abc import AsyncIterator

from pathfinder.ai.orchestration.deps import AgentDeps
from pathfinder.platform.event_schemas import PipelineConfig
from pathfinder.platform.types import JSONObject
from pathfinder.services.chat.streaming.producer import (
    produce_events,
    produce_plan_approved_events,
)


async def stream_pipeline(
    deps: AgentDeps,
    message: str,
    *,
    pipeline: PipelineConfig,
) -> AsyncIterator[JSONObject]:
    """Stream chat responses from the pydantic-ai pipeline as SSE-friendly events.

    The producer posts ``message_end`` as the absolute last event, then calls
    ``queue.shutdown()`` (Python 3.14).  The consumer reads until ``ShutDown``
    — no grace period, no sentinel, no timeout.

    NOTE: Does NOT emit ``message_start`` — the orchestrator (_chat_producer)
    emits the rich ``message_start`` with strategy context before calling us.
    """
    queue: asyncio.Queue[JSONObject] = asyncio.Queue()
    deps.event_queue = queue

    producer = asyncio.create_task(
        produce_events(deps, message, queue, pipeline)
    )
    try:
        while True:
            try:
                event = await queue.get()
            except asyncio.QueueShutDown:
                break
            yield event
    finally:
        deps.cancel_event.set()
        producer.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await producer


async def stream_pipeline_after_plan_approval(
    deps: AgentDeps,
    *,
    pipeline: PipelineConfig,
) -> AsyncIterator[JSONObject]:
    """Stream execution/verification events after a structured approval."""
    queue: asyncio.Queue[JSONObject] = asyncio.Queue()
    deps.event_queue = queue

    producer = asyncio.create_task(
        produce_plan_approved_events(deps, queue, pipeline)
    )
    try:
        while True:
            try:
                event = await queue.get()
            except asyncio.QueueShutDown:
                break
            yield event
    finally:
        deps.cancel_event.set()
        producer.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await producer
