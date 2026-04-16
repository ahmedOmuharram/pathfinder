from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.persistence.models import Message


class MessagesRepository:
    """Persistence for AI-SDK v6 ``UIMessage`` rows."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def insert_message(
        self,
        *,
        message_id: UUID,
        chat_id: UUID,
        role: str,
        parts: list[dict[str, Any]],
        metadata: dict[str, Any],
    ) -> None:
        """Add a new message row. Caller is responsible for ``commit``."""
        self.session.add(
            Message(
                id=message_id,
                chat_id=chat_id,
                role=role,
                parts=parts,
                metadata_=metadata,
            )
        )

    async def list_messages_for_chat(self, chat_id: UUID) -> list[Message]:
        """Return messages for a chat, oldest first."""
        stmt = (
            select(Message)
            .where(Message.chat_id == chat_id)
            .order_by(Message.created_at)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def mark_turn_completed(self, message_id: UUID) -> None:
        """Flag an assistant message as the verification-complete row of its turn.

        The autowrite path reads ``metadata.turnCompleted == true`` on
        verification messages to count successful turns without consulting
        the in-flight pipeline state.
        """
        message = await self.session.get(Message, message_id)
        if message is None:
            return
        updated = dict(message.metadata_ or {})
        updated["turnCompleted"] = True
        message.metadata_ = updated
