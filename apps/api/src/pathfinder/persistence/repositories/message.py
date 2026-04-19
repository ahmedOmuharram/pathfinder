from decimal import Decimal, InvalidOperation
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
        conversation_id: UUID,
        role: str,
        parts: list[dict[str, Any]],
        metadata: dict[str, Any],
    ) -> None:
        """Add a new message row. Caller is responsible for ``commit``."""
        self.session.add(
            Message(
                id=message_id,
                conversation_id=conversation_id,
                role=role,
                parts=parts,
                metadata_=metadata,
            )
        )

    async def list_messages_for_conversation(self, conversation_id: UUID) -> list[Message]:
        """Return messages for a chat, oldest first."""
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def sum_usage_for_conversation(
        self, conversation_id: UUID,
    ) -> tuple[int, Decimal]:
        """Sum ``metadata.usage.{totalTokens,costUsd}`` across all messages."""
        stmt = select(Message.metadata_).where(
            Message.conversation_id == conversation_id,
        )
        result = await self.session.execute(stmt)
        total_tokens = 0
        total_cost = Decimal(0)
        for (meta,) in result.all():
            if not isinstance(meta, dict):
                continue
            usage = meta.get("usage")
            if not isinstance(usage, dict):
                continue
            raw_tokens = usage.get("totalTokens")
            if isinstance(raw_tokens, int):
                total_tokens += raw_tokens
            raw_cost = usage.get("costUsd")
            if isinstance(raw_cost, (str, int, float)):
                try:
                    total_cost += Decimal(str(raw_cost))
                except InvalidOperation:
                    continue
        return total_tokens, total_cost

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
