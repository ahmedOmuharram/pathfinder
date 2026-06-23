from __future__ import annotations

import os
from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from pathfinder.ai.memory import lifespan as lifespan_module
from pathfinder.ai.memory.lifespan import lifespan_memory_store
from pathfinder.ai.memory.schemas import MemoryValue
from pathfinder.ai.memory.store import MemoryStore
from pathfinder.integrations.embeddings.prefixes import (
    SEARCH_DOCUMENT_PREFIX,
    SEARCH_QUERY_PREFIX,
)


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


@pytest.mark.asyncio
async def test_store_applies_asymmetric_nomic_prefixes(
    db_cleaner: None, patch_app_db_engine: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """End-to-end proof that puts embed ``search_document:`` text and searches
    embed ``search_query:`` text.

    The LangGraph Postgres store routes BOTH put and search through
    ``aembed_documents`` (it never calls ``aembed_query``), so asymmetric
    prefixes can only come from the text we hand it. A capturing embed records
    exactly what each path asks to embed, exercising the real store routing.
    """
    del db_cleaner, patch_app_db_engine
    database_url = os.environ["DATABASE_URL"]
    user_id = uuid4()
    embedded_texts: list[str] = []

    async def capturing_embed(texts: Sequence[str]) -> list[list[float]]:
        embedded_texts.extend(texts)
        unit = [1.0] + [0.0] * 511
        return [list(unit) for _ in texts]

    monkeypatch.setattr(lifespan_module, "embed_text", capturing_embed)

    async with lifespan_memory_store(database_url) as raw_store:
        store = MemoryStore(store=raw_store)
        await store.put(
            user_id=user_id,
            value=MemoryValue(
                kind="knowledge",
                name="surface_antigen_set",
                summary="merozoite surface proteins",
                tags=["malaria"],
                content={"fact": "verified"},
                created_at=datetime.now(UTC),
            ),
        )
        await store.semantic_search(
            user_id=user_id,
            kind="knowledge",
            query="vaccine targets",
            top_k=1,
        )

    document_texts = [t for t in embedded_texts if t.startswith(SEARCH_DOCUMENT_PREFIX)]
    query_texts = [t for t in embedded_texts if t.startswith(SEARCH_QUERY_PREFIX)]
    assert any("surface_antigen_set" in t for t in document_texts)
    assert query_texts == [f"{SEARCH_QUERY_PREFIX}vaccine targets"]
    # A query must never be embedded as a document, nor vice versa.
    assert not any(t.startswith(SEARCH_DOCUMENT_PREFIX) for t in query_texts)
    assert all(not t.startswith(SEARCH_QUERY_PREFIX) for t in document_texts)
