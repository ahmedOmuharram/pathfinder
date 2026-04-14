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
