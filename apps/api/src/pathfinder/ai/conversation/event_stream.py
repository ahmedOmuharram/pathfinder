from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

import asyncpg
from sqlalchemy import select
from sqlalchemy.engine import make_url

from pathfinder.persistence.models import ConversationEvent
from pathfinder.persistence.session import async_session_factory
from pathfinder.platform.config import get_settings
from pathfinder.platform.logging import get_logger

logger = get_logger(__name__)


def _asyncpg_dsn(database_url: str) -> str:
    url = make_url(database_url)
    if url.drivername.startswith("postgresql+"):
        url = url.set(drivername="postgresql")
    return url.render_as_string(hide_password=False)


async def _fetch_after(
    conversation_id: UUID, after: int,
) -> list[tuple[int, dict[str, Any]]]:
    async with async_session_factory() as session:
        rows = (
            await session.scalars(
                select(ConversationEvent)
                .where(
                    ConversationEvent.conversation_id == conversation_id,
                    ConversationEvent.id > after,
                )
                .order_by(ConversationEvent.id),
            )
        ).all()
        return [(r.id, r.chunk) for r in rows]


async def latest_event(
    conversation_id: UUID,
) -> tuple[int, dict[str, Any]] | None:
    async with async_session_factory() as session:
        row = await session.scalar(
            select(ConversationEvent)
            .where(ConversationEvent.conversation_id == conversation_id)
            .order_by(ConversationEvent.id.desc())
            .limit(1),
        )
        if row is None:
            return None
        return (row.id, row.chunk)


async def _drain_and_yield(
    conversation_id: UUID,
    last_sent: int,
    queue: asyncio.Queue[int],
    cancel: asyncio.Event,
) -> AsyncIterator[tuple[int, dict[str, Any]]]:
    while not cancel.is_set():
        try:
            await asyncio.wait_for(queue.get(), timeout=1.0)
        except TimeoutError:
            continue
        while not queue.empty():
            queue.get_nowait()
        for event_id, chunk in await _fetch_after(conversation_id, last_sent):
            if cancel.is_set():
                return
            yield event_id, chunk
            last_sent = event_id


async def replay_and_tail(
    *,
    conversation_id: UUID,
    after: int,
    cancel: asyncio.Event,
) -> AsyncIterator[tuple[int, dict[str, Any]]]:
    """Replay rows past ``after``, then tail new ones via ``LISTEN``."""
    last_sent = after
    for event_id, chunk in await _fetch_after(conversation_id, after):
        if cancel.is_set():
            return
        yield event_id, chunk
        last_sent = event_id

    channel = f"conversation_events:{conversation_id}"
    queue: asyncio.Queue[int] = asyncio.Queue()

    def on_notify(_conn: object, _pid: int, _channel: str, payload: str) -> None:
        try:
            queue.put_nowait(int(payload))
        except ValueError:
            logger.warning("pg_notify payload not an int", payload=payload)

    dsn = _asyncpg_dsn(get_settings().database_url)
    conn = await asyncpg.connect(dsn=dsn)
    try:
        await conn.add_listener(channel, on_notify)
        # Race-catch: a row could have landed between the SELECT above and
        # add_listener. Sweep once now that LISTEN is armed.
        for event_id, chunk in await _fetch_after(conversation_id, last_sent):
            if cancel.is_set():
                return
            yield event_id, chunk
            last_sent = event_id

        async for event_id, chunk in _drain_and_yield(
            conversation_id, last_sent, queue, cancel,
        ):
            yield event_id, chunk
    finally:
        await conn.close()


async def iter_sse(
    *, conversation_id: UUID, after: int,
) -> AsyncIterator[str]:
    cancel = asyncio.Event()
    try:
        async for event_id, chunk in replay_and_tail(
            conversation_id=conversation_id, after=after, cancel=cancel,
        ):
            yield _frame_event(event_id, chunk)
            if chunk.get("type") == "done":
                cancel.set()
                return
    except asyncio.CancelledError:
        cancel.set()
        raise


def _frame_event(event_id: int, chunk: dict[str, Any]) -> str:
    """SSE frame for a persisted chunk. Hand-rolled: pydantic-ai's
    ``VercelAIEventStream.encode_event`` needs ``BaseChunk`` instances and
    ``BaseChunk`` has no discriminator for dict-in rehydration.
    """
    payload = (
        "[DONE]"
        if chunk.get("type") == "done"
        else json.dumps(chunk, separators=(",", ":"))
    )
    return f"id: {event_id}\ndata: {payload}\n\n"
