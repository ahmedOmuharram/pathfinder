"""Vectorstore startup/bootstrap helpers."""

import asyncio

from veupath_chatbot.integrations.vectorstore.collections import (
    EXAMPLE_PLANS_V1,
    WDK_RECORD_TYPES_V1,
    WDK_SEARCHES_V1,
)
from veupath_chatbot.integrations.vectorstore.qdrant_store import QdrantStore
from veupath_chatbot.platform.logging import get_logger

logger = get_logger(__name__)

_KNOWN_DIMS: dict[str, int] = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
}


def _known_embedding_dims(model: str) -> int | None:
    """Best-effort embedding dimension lookup for common OpenAI models.

    This avoids a network call at API startup while still letting us create
    empty collections before ingestion runs.

    :param model: OpenAI model name (e.g. text-embedding-3-small).
    :returns: Dimension count or None if unknown.
    """
    return _KNOWN_DIMS.get((model or "").strip())


async def get_embedding_dim(model: str) -> int:
    """Return embedding dimension for *model*, using cache then OpenAI fallback.

    Prefer this over calling ``embed_one()`` just to discover vector size.
    """
    dim = _known_embedding_dims(model)
    if dim is not None:
        return dim

    from veupath_chatbot.integrations.embeddings.openai_embeddings import embed_one

    vec = await embed_one(text="dimension probe", model=model)
    dim = len(vec)
    # Cache for subsequent calls within the same process.
    _KNOWN_DIMS[(model or "").strip()] = dim
    return dim


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

    known = _known_embedding_dims(settings.embeddings_model)
    if known is not None:
        dim = known
    elif (
        settings.openai_api_key
        or settings.embeddings_base_url
        or settings.ollama_base_url
    ):
        dim = await get_embedding_dim(settings.embeddings_model)
    else:
        logger.warning(
            "RAG enabled but cannot infer embedding dimension; "
            "set OPENAI_API_KEY, EMBEDDINGS_BASE_URL, or configure Ollama.",
            embeddings_model=settings.embeddings_model,
        )
        return

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
