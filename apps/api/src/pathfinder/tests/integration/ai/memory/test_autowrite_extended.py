from __future__ import annotations

import os
from uuid import uuid4

import pytest

from pathfinder.ai.graph.state import PipelineState
from pathfinder.ai.memory.autowrite import auto_write_memories
from pathfinder.ai.memory.lifespan import lifespan_memory_store
from pathfinder.ai.memory.store import MemoryStore
from pathfinder.ai.memory.tombstones import TombstoneRepository
from pathfinder.persistence.models import User
from pathfinder.persistence.session import async_session_factory


@pytest.mark.asyncio
async def test_auto_write_gene_sets(
    db_cleaner: None, patch_app_db_engine: None,
) -> None:
    del db_cleaner, patch_app_db_engine
    database_url = os.environ["DATABASE_URL"]
    user_id = uuid4()
    async with async_session_factory() as session:
        session.add(User(id=user_id))
        await session.commit()

    state = PipelineState(
        chat_id=uuid4(),
        user_id=user_id,
        site_id="toxodb",
        mode="strategy",
        user_prompt="toxo bradyzoite",
        created_gene_set_ids=["gs-abc-123"],
    )

    async with lifespan_memory_store(database_url) as raw_store:
        mem_store = MemoryStore(store=raw_store)
        tombstones = TombstoneRepository(session_factory=async_session_factory)
        written = await auto_write_memories(
            store=mem_store, tombstones=tombstones, state=state,
        )
        assert written >= 1
        sets = await mem_store.list_all(user_id=user_id, kind="gene_set")
        assert len(sets) == 1
        assert sets[0].value.content["gene_set_id"] == "gs-abc-123"
