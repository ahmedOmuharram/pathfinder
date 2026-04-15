from __future__ import annotations

import os
from uuid import uuid4

import pytest

from pathfinder.ai.graph.state import PipelineState
from pathfinder.ai.memory.autowrite import auto_write_memories
from pathfinder.ai.memory.lifespan import lifespan_memory_store
from pathfinder.ai.memory.store import MemoryStore
from pathfinder.ai.memory.tombstones import TombstoneRepository
from pathfinder.domain.strategy.plan import StrategyPlan
from pathfinder.persistence.models import User
from pathfinder.persistence.session import async_session_factory


@pytest.mark.asyncio
async def test_auto_write_persists_strategy_on_verification_complete(
    db_cleaner: None, patch_app_db_engine: None,
) -> None:
    del db_cleaner, patch_app_db_engine
    database_url = os.environ["DATABASE_URL"]
    user_id = uuid4()
    chat_id = uuid4()

    async with async_session_factory() as session:
        session.add(User(id=user_id))
        await session.commit()

    plan = StrategyPlan.model_validate({
        "title": "Malaria transporters",
        "description": "Test plan",
        "rationale": "Needed",
        "steps": [],
        "connections": [],
    })
    state = PipelineState(
        chat_id=chat_id,
        user_id=user_id,
        site_id="plasmodb",
        mode="strategy",
        user_prompt="malaria transporters",
        active_plan=plan,
    )

    async with lifespan_memory_store(database_url) as raw_store:
        mem_store = MemoryStore(store=raw_store)
        tombstones = TombstoneRepository(session_factory=async_session_factory)
        written = await auto_write_memories(
            store=mem_store,
            tombstones=tombstones,
            state=state,
        )
        assert written >= 1
        strategies = await mem_store.list_all(user_id=user_id, kind="strategy")
        assert len(strategies) == 1
        assert strategies[0].value.site_id == "plasmodb"
