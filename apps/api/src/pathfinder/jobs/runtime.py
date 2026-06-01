from __future__ import annotations

import asyncio
from uuid import UUID

from pathfinder.ai.graph.runtime import Context
from pathfinder.domain.strategy.strategy_ast import (
    PersistedStrategyGraph,
    StrategyAst,
)
from pathfinder.persistence.models import Conversation
from pathfinder.platform.db import async_session_factory
from pathfinder.services.research.literature_search import LiteratureSearchService
from pathfinder.services.research.web_search import WebSearchService
from pathfinder.services.strategies.session_factory import build_strategy_session


async def build_worker_runtime_context(
    *,
    conversation_id: str,
    task_id: str,
) -> Context:
    del task_id
    async with async_session_factory() as session:
        conversation = await session.get(Conversation, UUID(conversation_id))
    if conversation is None:
        msg = f"chat {conversation_id} not found"
        raise LookupError(msg)

    plan_payload: StrategyAst | None = None
    raw_ast = conversation.strategy_ast
    if raw_ast and "root" in raw_ast:
        try:
            plan_payload = StrategyAst.model_validate(raw_ast)
        except ValueError, KeyError, TypeError:
            plan_payload = None

    strategy_session = build_strategy_session(
        site_id=conversation.site_id,
        strategy_graph=PersistedStrategyGraph(
            id=str(conversation.id),
            name=conversation.name,
            strategy_ast=plan_payload,
            wdk_strategy_id=conversation.wdk_strategy_id,
        ),
    )

    return Context(
        site_id=conversation.site_id,
        user_id=conversation.user_id,
        strategy_session=strategy_session,
        db_session_factory=async_session_factory,
        web_search_service=WebSearchService(),
        literature_search_service=LiteratureSearchService(),
        cancel_event=asyncio.Event(),
        experiment_id=conversation.experiment_id,
        memory_store=None,
    )
