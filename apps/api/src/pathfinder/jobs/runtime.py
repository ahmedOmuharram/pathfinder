"""Build a LangGraph-style ``Context`` for a worker-side tool invocation.

Worker processes have no request cycle, so per-chat context must be rebuilt
from durable state every time a deferred task runs. We load the ``Conversation`` row
(for site/user/experiment), hydrate an empty ``StrategySession``, and wire up
the same external services used in the request path. The memory store is not
attached here — ``run_durable_task`` (Phase 5) opens ``lifespan_memory_store``
per invocation and rebuilds the Context via ``dataclasses.replace`` so the
worker-side tool can do memory reads/writes.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

from pathfinder.ai.graph.runtime import Context
from pathfinder.persistence.models import Conversation
from pathfinder.persistence.session import async_session_factory
from pathfinder.services.research.literature_search import LiteratureSearchService
from pathfinder.services.research.web_search import WebSearchService
from pathfinder.services.strategies.session_factory import build_strategy_session


async def build_worker_runtime_context(
    *,
    conversation_id: str,
    task_id: str,
) -> Context:
    """Load durable chat state and return a Context suitable for worker tools."""
    del task_id  # reserved for future tracing hooks
    async with async_session_factory() as session:
        conversation = await session.get(Conversation, UUID(conversation_id))
    if conversation is None:
        msg = f"chat {conversation_id} not found"
        raise LookupError(msg)

    strategy_session = build_strategy_session(
        site_id=conversation.site_id,
        strategy_graph=None,
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
