"""Turn-cancellation service for conversations.

Stop writes a request row that the worker running the turn polls. When that
worker has been silent for longer than ``worker_dead_heartbeat_seconds``, Stop
also ends the turn here and now. A worker that died more recently than that
window still owns its turn, so Stop leaves the request for the maintenance
sweep to act on.
"""

from uuid import UUID

from assistant_core.persistence.models import ConversationEvent
from assistant_core.platform.db import async_session_factory
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.jobs.maintenance import release_dead_turn
from pathfinder.persistence.repositories import (
    ChatTurnCancellationRepository,
    ConversationRepository,
)
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
    # A live worker reads the request; a long-silent one reads nothing.
    await release_dead_turn(conversation_id)


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
    await release_dead_turn(conversation_id)
