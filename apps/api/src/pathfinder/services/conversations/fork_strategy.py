from __future__ import annotations

from uuid import UUID

from assistant_core.persistence.models import Conversation, Message
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.persistence.models import (
    ConversationStrategy,
    StrategyRevisionView,
)
from pathfinder.persistence.repositories.conversation_strategy import (
    strategy_view_of,
)
from pathfinder.persistence.repositories.strategy_revision import (
    StrategyRevisionRepository,
)
from pathfinder.platform.errors import ForkRefusedError
from pathfinder.services.strategies.materialize import (
    materialize_strategy_snapshot,
    snapshot_as_plan,
)
from pathfinder.services.strategies.revision_ops import revision_at_message


async def anchor_snapshot(
    session: AsyncSession,
    *,
    source_conversation_id: UUID,
    anchor: Message,
    strategy_row: ConversationStrategy | None,
) -> StrategyRevisionView | None:
    """The strategy the anchor message was answered against.

    ``None`` means the fork starts with no strategy. A thread that holds a
    strategy but no history at all cannot be reproduced, so it is refused
    rather than copied at its latest state.
    """
    if strategy_row is None:
        return None
    snapshot = await revision_at_message(session, message=anchor)
    if snapshot is not None:
        return snapshot
    if await StrategyRevisionRepository(session).has_any(source_conversation_id):
        # Every snapshot postdates the anchor: nothing was built yet.
        return None
    msg = (
        "This chat predates the strategy history, so a branch cannot "
        "reproduce the strategy it had at that message."
    )
    raise ForkRefusedError(msg)


async def write_forked_strategy(
    session: AsyncSession,
    *,
    source: Conversation,
    snapshot: StrategyRevisionView,
    strategy_row: ConversationStrategy,
    new_conversation_id: UUID,
    anchor_message_id: UUID,
) -> None:
    """Push the snapshot as the fork's own WDK strategy and store it."""
    source_strategy = strategy_view_of(strategy_row)
    materialized = (
        snapshot_as_plan(
            snapshot.strategy_ast,
            record_type=snapshot.record_type,
            step_count=snapshot.step_count,
        )
        if snapshot.wdk_strategy_id is None
        else await materialize_strategy_snapshot(
            site_id=source.site_id,
            conversation_id=new_conversation_id,
            name=source.name,
            strategy_ast=snapshot.strategy_ast,
        )
    )
    session.add(
        ConversationStrategy(
            conversation_id=new_conversation_id,
            record_type=materialized.record_type,
            strategy_ast=materialized.strategy_ast,
            step_count=materialized.step_count,
            gene_set_id=source_strategy.gene_set_id,
            gene_set_auto_imported=source_strategy.gene_set_auto_imported,
            experiment_id=source_strategy.experiment_id,
            wdk_strategy_id=materialized.wdk_strategy_id,
            # The fork still embeds the imported subtrees, so it keeps
            # the references.
            imported_saved_strategy_ids=list(
                source_strategy.imported_saved_strategy_ids,
            ),
        ),
    )
    await session.flush()
    await StrategyRevisionRepository(session).record(
        new_conversation_id,
        strategy_view_of(
            await session.get(ConversationStrategy, new_conversation_id),
        ),
        message_id=anchor_message_id,
    )
