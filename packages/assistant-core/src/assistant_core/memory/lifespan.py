from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langgraph.store.postgres.aio import AsyncPostgresStore
from langgraph.store.postgres.base import PostgresIndexConfig

from assistant_core.conversation.checkpointer import to_psycopg_url
from assistant_core.embeddings.embedder import EMBEDDING_DIMENSIONS
from assistant_core.memory.embedding import embed_text


@asynccontextmanager
async def lifespan_memory_store(
    database_url: str,
) -> AsyncIterator[AsyncPostgresStore]:
    """Open the LangGraph ``AsyncPostgresStore`` with vector indexing.

    ``fields`` lists the stored payload keys LangGraph embeds, one
    vector per field per put. We point it at a single synthetic
    ``_embed_text`` key populated by :func:`assistant_core.memory.store._dump_for_store`
    so every memory gets exactly one embedding (kind + name + tags +
    summary concatenated). Listing multiple raw fields would cost 4x per
    put and force ``Item.score`` to reflect best-field-match rather than
    combined semantic similarity.
    """
    psycopg_url = to_psycopg_url(database_url)
    index_config: PostgresIndexConfig = {
        "dims": EMBEDDING_DIMENSIONS,
        "embed": embed_text,
        "fields": ["_embed_text"],
        "distance_type": "cosine",
    }
    async with AsyncPostgresStore.from_conn_string(
        psycopg_url,
        index=index_config,
    ) as store:
        await store.setup()
        yield store
