from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import text

from assistant_core.persistence.models import ConversationEvent
from assistant_core.platform.db import async_session_factory


async def append_chunk(
    *,
    conversation_id: UUID,
    chunk: dict[str, Any],
    turn_id: UUID | None = None,
) -> int:
    """Append one chunk to a thread's log and broadcast its cursor.

    A chunk that belongs to no turn, such as a durable task's progress
    between turns, carries no ``turn_id``.
    """
    channel = f"conversation_events:{conversation_id}"
    async with async_session_factory() as session:
        row = ConversationEvent(
            conversation_id=conversation_id,
            turn_id=turn_id,
            chunk=chunk,
        )
        session.add(row)
        await session.flush()
        event_id = row.id
        await session.execute(
            text("SELECT pg_notify(:channel, :payload)"),
            {"channel": channel, "payload": str(event_id)},
        )
        await session.commit()
        return event_id


class ChatWriter(Protocol):
    """The chunk-sink contract ``run_turn`` drives. ``ChatEventWriter``
    persists to Postgres; devtools supply a console implementation."""

    conversation_id: UUID
    turn_id: UUID

    async def write(self, chunk: dict[str, Any]) -> int: ...


class ChatEventWriter:
    """Persists a chunk row and broadcasts ``NOTIFY`` on the chat channel.

    One writer instance per (conversation, turn). Every ``write(chunk)``
    returns the assigned event id so callers can surface the cursor.
    """

    def __init__(self, *, conversation_id: UUID, turn_id: UUID) -> None:
        self.conversation_id = conversation_id
        self.turn_id = turn_id

    async def write(self, chunk: dict[str, Any]) -> int:
        return await append_chunk(
            conversation_id=self.conversation_id,
            chunk=chunk,
            turn_id=self.turn_id,
        )
