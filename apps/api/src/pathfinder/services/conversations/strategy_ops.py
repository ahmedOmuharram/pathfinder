"""Strategy-mutation operations on a conversation's persisted graph.

Split out of ConversationService: these four operations all load the
conversation's ``PersistedStrategyGraph`` and run a strategy-session
mutation, distinct from plain conversation CRUD.
"""

from dataclasses import dataclass
from uuid import UUID

from assistant_core.persistence.models import Conversation
from assistant_core.platform.db import async_session_factory
from assistant_core.platform.types import JSONObject

from pathfinder.domain.strategy.operations import GraphOperation
from pathfinder.domain.strategy.ops import CombineOp
from pathfinder.domain.strategy.strategy_ast import (
    PersistedStrategyGraph,
    StrategyAst,
)
from pathfinder.persistence.models import ConversationStrategyView
from pathfinder.persistence.repositories import ConversationRepository
from pathfinder.platform.errors import ErrorCode, NotFoundError, ValidationError
from pathfinder.services.conversations.authz import (
    get_owned_conversation_or_404,
    get_owned_thread_or_404,
)
from pathfinder.services.conversations.responses import (
    ConversationResponse,
    build_conversation_response,
    build_conversation_summary,
)
from pathfinder.services.strategies.commit import apply_and_commit
from pathfinder.services.strategies.context import StrategyMutationContext
from pathfinder.services.strategies.insert_saved import (
    InsertSavedResult,
    insert_saved_into_conversation,
)
from pathfinder.services.strategies.save_substrategy import (
    SavedSubstrategyResult,
    save_subtree_as_strategy,
)
from pathfinder.services.strategies.session_factory import build_strategy_session


@dataclass(frozen=True)
class SaveSubstrategyParams:
    site_id: str
    step_id: str
    name: str
    description: str | None


@dataclass(frozen=True)
class InsertSavedParams:
    site_id: str
    target_step_id: str
    saved_wdk_strategy_id: int
    operator: CombineOp


def _persisted_graph(
    conversation: Conversation,
    strategy: ConversationStrategyView,
) -> PersistedStrategyGraph:
    return PersistedStrategyGraph(
        id=str(conversation.id),
        name=conversation.name,
        strategy_ast=StrategyAst.model_validate(strategy.strategy_ast),
        wdk_strategy_id=strategy.wdk_strategy_id,
    )


async def get_ast(
    repo: ConversationRepository,
    conversation_id: UUID,
    user_id: UUID,
) -> JSONObject:
    _conversation, strategy = await get_owned_thread_or_404(
        repo, conversation_id, user_id
    )
    strategy_ast = strategy.strategy_ast
    if not strategy_ast:
        raise NotFoundError(
            code=ErrorCode.STRATEGY_NOT_FOUND,
            title="Strategy has no plan AST",
        )
    return strategy_ast


async def restore(
    repo: ConversationRepository,
    conversation_id: UUID,
    user_id: UUID,
) -> ConversationResponse:
    conversation = await get_owned_conversation_or_404(repo, conversation_id, user_id)
    if conversation.dismissed_at is None:
        raise ValidationError(
            detail="Strategy is not dismissed",
            errors=[
                {
                    "path": "strategyId",
                    "message": "Not dismissed",
                    "code": "INVALID_STATE",
                },
            ],
        )
    await repo.restore(conversation_id)
    updated = await repo.get_with_strategy(conversation_id)
    if not updated:
        raise NotFoundError(
            code=ErrorCode.STRATEGY_NOT_FOUND,
            title="Strategy not found",
        )
    return build_conversation_summary(*updated)


async def apply_operation(
    repo: ConversationRepository,
    conversation_id: UUID,
    user_id: UUID,
    *,
    site_id: str,
    op: GraphOperation,
) -> ConversationResponse:
    conversation, strategy = await get_owned_thread_or_404(
        repo, conversation_id, user_id
    )
    if not strategy.strategy_ast:
        raise NotFoundError(
            code=ErrorCode.STRATEGY_NOT_FOUND,
            title="Strategy AST missing",
        )
    ctx = StrategyMutationContext(
        site_id=site_id,
        strategy_session=build_strategy_session(
            site_id=site_id,
            strategy_graph=_persisted_graph(conversation, strategy),
        ),
        conversation_id=conversation_id,
        db_session_factory=async_session_factory,
    )
    await apply_and_commit(deps=ctx, op=op)
    refreshed = await repo.get_with_strategy(conversation_id)
    if refreshed is None:
        raise NotFoundError(
            code=ErrorCode.STRATEGY_NOT_FOUND,
            title="Strategy not found after commit",
        )
    return build_conversation_response(*refreshed)


async def save_substrategy(
    repo: ConversationRepository,
    conversation_id: UUID,
    user_id: UUID,
    params: SaveSubstrategyParams,
) -> SavedSubstrategyResult:
    conversation, strategy = await get_owned_thread_or_404(
        repo, conversation_id, user_id
    )
    if not strategy.strategy_ast:
        raise ValidationError(
            title="conversation has no strategy",
            detail="cannot save substrategy from an empty conversation",
        )
    session = build_strategy_session(
        site_id=params.site_id,
        strategy_graph=_persisted_graph(conversation, strategy),
    )
    graph = session.get_graph(None)
    if graph is None or params.step_id not in graph.steps:
        raise NotFoundError(
            code=ErrorCode.STEP_NOT_FOUND,
            title="step not found",
            detail=(
                f"step {params.step_id!r} not found in conversation {conversation_id}"
            ),
        )
    return await save_subtree_as_strategy(
        session=session,
        site_id=params.site_id,
        source_step_id=params.step_id,
        name=params.name,
        description=params.description,
    )


async def count_saved_strategy_consumers(
    repo: ConversationRepository,
    user_id: UUID,
    site_id: str,
) -> dict[int, int]:
    return await repo.count_consumers_per_saved_strategy(user_id, site_id)


async def insert_saved(
    repo: ConversationRepository,
    conversation_id: UUID,
    user_id: UUID,
    params: InsertSavedParams,
) -> InsertSavedResult:
    conversation, strategy = await get_owned_thread_or_404(
        repo, conversation_id, user_id
    )
    if not strategy.strategy_ast:
        raise ValidationError(
            title="conversation has no strategy",
            detail="cannot insert into an empty conversation",
        )
    session = build_strategy_session(
        site_id=params.site_id,
        strategy_graph=_persisted_graph(conversation, strategy),
    )
    return await insert_saved_into_conversation(
        session=session,
        site_id=params.site_id,
        conversation_id=conversation_id,
        db_session_factory=async_session_factory,
        target_step_id=params.target_step_id,
        saved_wdk_strategy_id=params.saved_wdk_strategy_id,
        operator=params.operator,
    )
