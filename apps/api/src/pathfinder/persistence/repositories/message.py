"""Repository for the parts-based messages table.

New in the chat/SSE overhaul (Task 3, Apr 2026). Sits alongside the legacy
``StreamRepository`` until the old chat pipeline is removed.
"""

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.persistence.models import Message


class MessagesRepository:
    """Persistence for AI-SDK v6 ``UIMessage`` rows (parts-based).

    Two write paths:
      * ``insert_message`` — single insert at turn end for the finished
        assistant message (or any single user/system message).
      * ``upsert_message`` — upsert on ``id`` for mid-stream checkpoints,
        so a tab-close during a long-running turn doesn't lose the whole
        message (resume substitute for v1).
    """

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

    async def upsert_message(
        self,
        *,
        message_id: UUID,
        chat_id: UUID,
        role: str,
        parts: list[dict[str, Any]],
        metadata: dict[str, Any],
    ) -> None:
        """Upsert on message id — used for periodic mid-stream checkpoints.

        The upserted row preserves the original ``created_at`` (and ``role``
        + ``chat_id``), only ``parts`` and ``metadata`` advance as the turn
        streams.
        """
        stmt = (
            insert(Message)
            .values(
                id=message_id,
                chat_id=chat_id,
                role=role,
                parts=parts,
                metadata_=metadata,
            )
            .on_conflict_do_update(
                index_elements=[Message.id],
                set_={"parts": parts, "metadata": metadata},
            )
        )
        await self.session.execute(stmt)

    async def list_messages_for_chat(self, chat_id: UUID) -> list[Message]:
        """Return messages for a chat, oldest first."""
        stmt = (
            select(Message)
            .where(Message.chat_id == chat_id)
            .order_by(Message.created_at)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def latest_assistant_model_history(
        self, chat_id: UUID,
    ) -> list[dict[str, Any]]:
        stmt = (
            select(Message)
            .where(Message.chat_id == chat_id, Message.role == "assistant")
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return []
        history = row.metadata_.get("modelHistory")
        return history if isinstance(history, list) else []
