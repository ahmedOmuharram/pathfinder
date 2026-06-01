"""Turn-cancellation service for conversations."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.persistence.models import ConversationEvent
from pathfinder.persistence.repositories import (
    ChatTurnCancellationRepository,
    ConversationRepository,
)
from pathfinder.platform.db import async_session_factory
from pathfinder.services.conversations.authz import get_owned_or_404


async def cancel_turn(
    session: AsyncSession,
    *,
    conversation_id: UUID,
    turn_id: UUID,
    user_id: UUID,
) -> None:
    await get_owned_or_404(
        ConversationRepository(session),
        conversation_id,
        user_id,
    )
    repo = ChatTurnCancellationRepository(session_factory=async_session_factory)
    await repo.request_cancel(conversation_id=conversation_id, turn_id=turn_id)


async def cancel_active_turn(
    session: AsyncSession,
    *,
    conversation_id: UUID,
    user_id: UUID,
) -> None:
    await get_owned_or_404(
        ConversationRepository(session),
        conversation_id,
        user_id,
    )
    row = await session.scalar(
        select(ConversationEvent)
        .where(
            ConversationEvent.conversation_id == conversation_id,
            ConversationEvent.task_id.is_(None),
        )
        .order_by(ConversationEvent.id.desc())
        .limit(1),
    )
    if row is None or row.chunk.get("type") == "done" or row.turn_id is None:
        return
    repo = ChatTurnCancellationRepository(session_factory=async_session_factory)
    await repo.request_cancel(conversation_id=conversation_id, turn_id=row.turn_id)
