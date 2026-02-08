"""Vectorstore startup/bootstrap helpers."""

from __future__ import annotations

import asyncio

from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.services.vectorstore.collections import (
    EXAMPLE_PLANS_V1,
    WDK_RECORD_TYPES_V1,
    WDK_SEARCHES_V1,
)
from veupath_chatbot.services.vectorstore.qdrant_store import QdrantStore

logger = get_logger(__name__)


def _known_embedding_dims(model: str) -> int | None:
    """Best-effort embedding dimension lookup for common OpenAI models.

    This avoids a network call at API startup while still letting us create
    empty collections before ingestion runs.
    """
    m = (model or "").strip()
    if m == "text-embedding-3-small":
        return 1536
    if m == "text-embedding-3-large":
        return 3072
    return None


async def ensure_rag_collections() -> None:
    """Ensure core Qdrant collections exist.

    This creates *empty* collections so that RAG lookups do not fail with 404
    when ingestion has not been run yet.
    """
    from veupath_chatbot.platform.config import get_settings

    settings = get_settings()
    if not settings.rag_enabled:
        return

    store = QdrantStore.from_settings()

    dim = _known_embedding_dims(settings.embeddings_model)
    if dim is None:
        # Fallback: compute embedding dimension via a real embedding request.
        # This requires an API key; if absent, we skip with a clear log message.
        if not settings.openai_api_key:
            logger.warning(
                "RAG enabled but cannot infer embedding dimension; "
                "set OPENAI_API_KEY or use a known embeddings_model.",
                embeddings_model=settings.embeddings_model,
            )
            return
        from veupath_chatbot.services.embeddings.openai_embeddings import embed_one

        dim = len(
            await embed_one(text="dimension probe", model=settings.embeddings_model)
        )

    # Ensure the main discovery/example collections exist (even if empty).
    #
    # In Docker Compose, Qdrant may be "started" but not yet ready to accept
    # requests. Retry briefly to avoid flakey startup behavior.
    last_exc: Exception | None = None
    for attempt in range(8):
        try:
            await store.ensure_collection(name=WDK_RECORD_TYPES_V1, vector_size=dim)
            await store.ensure_collection(name=WDK_SEARCHES_V1, vector_size=dim)
            await store.ensure_collection(name=EXAMPLE_PLANS_V1, vector_size=dim)
            return
        except Exception as exc:  # pragma: no cover
            last_exc = exc
            await asyncio.sleep(0.25 * (attempt + 1))

    logger.warning(
        "Unable to ensure Qdrant collections after retries",
        error=str(last_exc) if last_exc else None,
    )
