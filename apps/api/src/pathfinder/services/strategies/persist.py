"""Persist a strategy graph's AST to its conversation row.

Extracted from the legacy auto-build hook so the new declarative build
service can persist without depending on the doomed hook chain. Takes the
strategy advisory lock for the merge+commit window only — not for any
WDK push above the call site.
"""

from __future__ import annotations

from sqlalchemy import text

from pathfinder.domain.strategy.ast import walk_step_tree
from pathfinder.domain.strategy.session import StrategyGraph
from pathfinder.domain.strategy.strategy_ast import StrategyAst
from pathfinder.persistence.models import Conversation
from pathfinder.persistence.repositories import ConversationRepository
from pathfinder.persistence.repositories.conversation import ConversationUpdate
from pathfinder.platform.errors import AppError
from pathfinder.platform.logging import get_logger
from pathfinder.services.strategies.context import StrategyMutationContext
from pathfinder.services.strategies.sync import SyncResult

logger = get_logger(__name__)


async def persist_strategy_ast_to_conversation(
    *,
    deps: StrategyMutationContext,
    graph: StrategyGraph,
    sync_result: SyncResult | None,
) -> None:
    """Write ``conversations.strategy_ast`` from the current graph.

    Inside an advisory lock keyed on the conversation id so concurrent
    user PATCHes don't race. Re-fetches the row inside the lock to merge
    any persisted ``wdk_step_ids`` the agent didn't see this turn.

    On a partial WDK push the caller passes ``sync_result=None`` so the
    new ``wdk_strategy_id`` is not written; only the incremental
    ``wdk_step_ids`` land.
    """
    if deps.conversation_id is None or deps.db_session_factory is None:
        return
    sync_state = deps.strategy_session.sync_state
    agent_ast = graph.to_strategy_ast(sync_state=sync_state)
    if agent_ast is None:
        return
    try:
        async with deps.db_session_factory() as session:
            await session.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"),
                {"k": f"strategy:{deps.conversation_id}"},
            )
            repo = ConversationRepository(session)
            current = await repo.get_by_id(deps.conversation_id)
            merged_ast = _merge_agent_ast_into_current(current, agent_ast)
            wdk_strategy_id_to_write = (
                sync_result.wdk_strategy_id
                if sync_result is not None
                else (current.wdk_strategy_id if current is not None else None)
            )
            await repo.update_conversation(
                deps.conversation_id,
                ConversationUpdate(
                    strategy_ast=merged_ast,
                    record_type=merged_ast.record_type or None,
                    wdk_strategy_id=wdk_strategy_id_to_write,
                    wdk_strategy_id_set=sync_result is not None,
                    step_count=len(walk_step_tree(merged_ast.root)),
                ),
            )
            await session.commit()
    except (AppError, OSError, RuntimeError) as exc:
        logger.warning(
            "Failed to persist strategy AST to conversation",
            conversation_id=str(deps.conversation_id),
            error=str(exc),
        )


def _merge_agent_ast_into_current(
    current: Conversation | None,
    agent_ast: StrategyAst,
) -> StrategyAst:
    """Write the agent's AST but preserve persisted ``wdk_step_ids`` it lacks.

    The agent owns the graph topology (it just mutated it). The persisted
    ``wdk_step_ids`` may include steps the agent already knows about; the
    union keeps any IDs a concurrent writer landed for steps the agent
    did not push this turn. When persisted state is missing entirely
    (fresh chat), use the agent view as-is.
    """
    if current is None or not current.strategy_ast:
        return agent_ast
    persisted = StrategyAst.model_validate(current.strategy_ast)
    merged_step_ids = dict(persisted.wdk_step_ids or {})
    merged_step_ids.update(agent_ast.wdk_step_ids or {})
    return agent_ast.model_copy(update={"wdk_step_ids": merged_step_ids})
