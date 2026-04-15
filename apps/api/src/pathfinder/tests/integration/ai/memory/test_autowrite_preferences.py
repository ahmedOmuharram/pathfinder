from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from pathfinder.ai.graph.state import PipelineState
from pathfinder.ai.memory.autowrite import auto_write_memories
from pathfinder.ai.memory.lifespan import lifespan_memory_store
from pathfinder.ai.memory.store import MemoryStore
from pathfinder.ai.memory.tombstones import TombstoneRepository
from pathfinder.persistence.models import Chat, Message, User
from pathfinder.persistence.session import async_session_factory


@pytest.mark.asyncio
async def test_preferences_autowrite_only_after_three_successes(
    db_cleaner: None, patch_app_db_engine: None,
) -> None:
    del db_cleaner, patch_app_db_engine
    database_url = os.environ["DATABASE_URL"]
    user_id = uuid4()
    async with async_session_factory() as session:
        session.add(User(id=user_id))
        await session.flush()
        # Seed 3 prior completed chats on plasmodb so this becomes the 4th success.
        for i in range(3):
            cid = uuid4()
            session.add(
                Chat(id=cid, user_id=user_id, site_id="plasmodb", name=f"old-{i}")
            )
            await session.flush()
            session.add(
                Message(
                    id=uuid4(),
                    chat_id=cid,
                    role="assistant",
                    parts=[],
                    metadata_={
                        "phase": "verification",
                        "phaseDecision": {"next_action": "complete"},
                    },
                    created_at=datetime.now(UTC) - timedelta(days=i + 1),
                )
            )
        await session.commit()

    state = PipelineState(
        chat_id=uuid4(),
        user_id=user_id,
        site_id="plasmodb",
        mode="strategy",
        user_prompt="another",
    )

    async with lifespan_memory_store(database_url) as raw_store:
        mem_store = MemoryStore(store=raw_store)
        tombstones = TombstoneRepository(session_factory=async_session_factory)
        await auto_write_memories(
            store=mem_store, tombstones=tombstones, state=state,
        )
        prefs = await mem_store.list_all(user_id=user_id, kind="preference")
        assert any(p.value.content.get("preferred_site") == "plasmodb" for p in prefs)


@pytest.mark.asyncio
async def test_preferences_not_written_with_fewer_than_three_successes(
    db_cleaner: None, patch_app_db_engine: None,
) -> None:
    del db_cleaner, patch_app_db_engine
    database_url = os.environ["DATABASE_URL"]
    user_id = uuid4()
    async with async_session_factory() as session:
        session.add(User(id=user_id))
        await session.flush()
        # Only 2 prior successes — below the threshold.
        for i in range(2):
            cid = uuid4()
            session.add(
                Chat(id=cid, user_id=user_id, site_id="plasmodb", name=f"old-{i}")
            )
            await session.flush()
            session.add(
                Message(
                    id=uuid4(),
                    chat_id=cid,
                    role="assistant",
                    parts=[],
                    metadata_={
                        "phase": "verification",
                        "phaseDecision": {"next_action": "complete"},
                    },
                    created_at=datetime.now(UTC) - timedelta(days=i + 1),
                )
            )
        await session.commit()

    state = PipelineState(
        chat_id=uuid4(),
        user_id=user_id,
        site_id="plasmodb",
        mode="strategy",
        user_prompt="another",
    )

    async with lifespan_memory_store(database_url) as raw_store:
        mem_store = MemoryStore(store=raw_store)
        tombstones = TombstoneRepository(session_factory=async_session_factory)
        await auto_write_memories(
            store=mem_store, tombstones=tombstones, state=state,
        )
        prefs = await mem_store.list_all(user_id=user_id, kind="preference")
        assert prefs == []
