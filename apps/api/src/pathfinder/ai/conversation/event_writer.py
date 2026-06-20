from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import text

from pathfinder.persistence.models import ConversationEvent
from pathfinder.platform.db import async_session_factory


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
        self._channel = f"conversation_events:{conversation_id}"

    async def write(self, chunk: dict[str, Any]) -> int:
        async with async_session_factory() as session:
            row = ConversationEvent(
                conversation_id=self.conversation_id,
                turn_id=self.turn_id,
                chunk=chunk,
            )
            session.add(row)
            await session.flush()
            event_id = row.id
            await session.execute(
                text("SELECT pg_notify(:channel, :payload)"),
                {"channel": self._channel, "payload": str(event_id)},
            )
            await session.commit()
            return event_id
