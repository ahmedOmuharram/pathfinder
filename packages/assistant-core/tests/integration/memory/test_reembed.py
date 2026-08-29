from __future__ import annotations

import os
from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from assistant_core.embeddings.embedder import EMBEDDING_DIMENSIONS
from assistant_core.memory import lifespan as lifespan_module
from assistant_core.memory.lifespan import lifespan_memory_store
from assistant_core.memory.reembed import reembed_all_memories
from assistant_core.memory.schemas import MemoryValue
from assistant_core.memory.store import MemoryStore


@pytest.mark.asyncio
async def test_reembed_reputs_every_memory_with_current_format(
    db_cleaner: None, patch_app_db_engine: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Re-embed touches every stored memory across users and kinds.

    It keeps the key and the value, and re-embeds the current
    ``format_embedded_string`` text, so a stored vector matches how a query is
    embedded now.
    """
    del db_cleaner, patch_app_db_engine
    database_url = os.environ["DATABASE_URL"]
    user_a, user_b = uuid4(), uuid4()
    embedded_texts: list[str] = []

    async def capturing_embed(texts: Sequence[str]) -> list[list[float]]:
        embedded_texts.extend(texts)
        unit = [1.0] + [0.0] * (EMBEDDING_DIMENSIONS - 1)
        return [list(unit) for _ in texts]

    monkeypatch.setattr(lifespan_module, "embed_text", capturing_embed)

    async with lifespan_memory_store(database_url) as raw_store:
        store = MemoryStore(store=raw_store)
        await store.put(
            user_id=user_a,
            value=MemoryValue(
                kind="gene_set",
                name="set_alpha",
                summary="alpha genes",
                tags=["a"],
                content={"gene_ids": ["PF3D7_0102500"]},
                created_at=datetime.now(UTC),
            ),
        )
        await store.put(
            user_id=user_b,
            value=MemoryValue(
                kind="knowledge",
                name="fact_beta",
                summary="beta fact",
                tags=["b"],
                content={"fact": "verified"},
                created_at=datetime.now(UTC),
            ),
        )

        embedded_texts.clear()
        count = await reembed_all_memories(store)

        assert count == 2
        document_texts = sorted(embedded_texts)
        assert len(document_texts) == 2
        assert any("set_alpha" in t for t in document_texts)
        assert any("fact_beta" in t for t in document_texts)

        # Keys + values are preserved (re-put in place, not duplicated).
        alpha = await store.list_all(user_id=user_a, kind="gene_set")
        beta = await store.list_all(user_id=user_b, kind="knowledge")
        assert len(alpha) == 1
        assert len(beta) == 1
        assert alpha[0].value.name == "set_alpha"
        assert alpha[0].value.content == {"gene_ids": ["PF3D7_0102500"]}
        assert beta[0].value.name == "fact_beta"
