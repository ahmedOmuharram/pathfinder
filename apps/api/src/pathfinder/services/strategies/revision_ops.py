"""Reading and restoring the strategy a thread held at a chosen point."""

from __future__ import annotations

from uuid import UUID

from assistant_core.persistence.models import Message
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.domain.strategy.revision import (
    parse_strategy_ast,
    without_wdk_readings,
)
from pathfinder.persistence.models import StrategyRevisionView
from pathfinder.persistence.repositories.conversation import ConversationRepository
from pathfinder.persistence.repositories.conversation_update import ConversationUpdate
from pathfinder.persistence.repositories.strategy_revision import (
    StrategyRevisionRepository,
)

__all__ = [
    "discard_turn_strategy_writes",
    "restore_revision",
    "revision_at_message",
]


async def revision_at_message(
    session: AsyncSession,
    *,
    message: Message,
) -> StrategyRevisionView | None:
    """The strategy snapshot in force at ``message``.

    A snapshot the message names wins; otherwise the newest snapshot written
    no later than the message.
    """
    repo = StrategyRevisionRepository(session)
    named = await repo.named_by(message.conversation_id, message_id=message.id)
    if named is not None:
        return named
    return await repo.at_or_before(message.conversation_id, message.created_at)


async def restore_revision(
    session: AsyncSession,
    *,
    revision: StrategyRevisionView,
) -> None:
    """Write a thread's strategy back to one of its snapshots."""
    ast = parse_strategy_ast(without_wdk_readings(revision.strategy_ast))
    repo = ConversationRepository(session)
    if ast is None:
        await repo.clear_strategy(revision.conversation_id)
        return
    await repo.update_conversation(
        revision.conversation_id,
        ConversationUpdate(
            strategy_ast=ast,
            record_type=revision.record_type,
            step_count=revision.step_count,
            wdk_strategy_id=revision.wdk_strategy_id,
            wdk_strategy_id_set=True,
            estimated_size=None,
            estimated_size_set=True,
        ),
    )


async def discard_turn_strategy_writes(
    session: AsyncSession,
    *,
    conversation_id: UUID,
    pre_turn_revision_id: int | None,
) -> bool:
    """Undo the strategy a stopped turn had already written.

    ``pre_turn_revision_id`` is the newest snapshot the thread held when the
    turn opened; ``None`` means it held no strategy at all. Reports whether
    anything was undone.
    """
    repo = StrategyRevisionRepository(session)
    removed = await repo.delete_newer_than(
        conversation_id,
        revision_row_id=pre_turn_revision_id,
    )
    if removed == 0:
        return False
    if pre_turn_revision_id is None:
        await ConversationRepository(session).clear_strategy(conversation_id)
        return True
    snapshot = await repo.latest(conversation_id)
    if snapshot is None:
        return False
    await restore_revision(session, revision=snapshot)
    return True
