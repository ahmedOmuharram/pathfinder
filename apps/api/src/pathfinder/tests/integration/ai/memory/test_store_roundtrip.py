from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from pathfinder.ai.memory.lifespan import lifespan_memory_store
from pathfinder.ai.memory.schemas import MemoryValue
from pathfinder.ai.memory.store import MemoryStore


@pytest.mark.asyncio
async def test_memory_store_put_and_get(
    db_cleaner: None, patch_app_db_engine: None
) -> None:
    del db_cleaner, patch_app_db_engine
    database_url = os.environ["DATABASE_URL"]
    user_id = uuid4()
    async with lifespan_memory_store(database_url) as raw_store:
        store = MemoryStore(store=raw_store)
        value = MemoryValue(
            kind="gene_set",
            name="test_set",
            summary="a description",
            tags=["tag"],
            content={"gene_ids": ["PF3D7_0102500"]},
            created_at=datetime.now(UTC),
        )
        stored_key = await store.put(user_id=user_id, value=value)

        listed = await store.list_all(user_id=user_id, kind="gene_set")
        assert len(listed) == 1
        assert listed[0].key == stored_key
        assert listed[0].value.name == "test_set"


@pytest.mark.asyncio
async def test_memory_store_search_returns_relevant_first(
    db_cleaner: None, patch_app_db_engine: None
) -> None:
    del db_cleaner, patch_app_db_engine
    database_url = os.environ["DATABASE_URL"]
    user_id = uuid4()
    async with lifespan_memory_store(database_url) as raw_store:
        store = MemoryStore(store=raw_store)
        await store.put(
            user_id=user_id,
            value=MemoryValue(
                kind="knowledge",
                name="malaria_drug_targets",
                summary="plasmodium falciparum validated drug targets phase 2",
                tags=["malaria", "drug"],
                content={"fact": "verified"},
                created_at=datetime.now(UTC),
            ),
        )
        await store.put(
            user_id=user_id,
            value=MemoryValue(
                kind="knowledge",
                name="cookie_recipe",
                summary="chocolate chip cookies with brown butter",
                tags=["recipe"],
                content={"fact": "other"},
                created_at=datetime.now(UTC),
            ),
        )

        hits = await store.semantic_search(
            user_id=user_id,
            kind="knowledge",
            query="antimalarial drug targets",
            top_k=2,
        )
        assert len(hits) == 2
        assert hits[0].value.name == "malaria_drug_targets"
        assert hits[0].score is not None
        assert hits[0].score >= hits[1].score if hits[1].score is not None else True
