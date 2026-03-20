from collections.abc import Sequence
from itertools import batched
from typing import Any, cast

from qdrant_client import AsyncQdrantClient

from veupath_chatbot.integrations.embeddings.openai_embeddings import OpenAIEmbeddings
from veupath_chatbot.integrations.vectorstore.qdrant_store import QdrantStore
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject, JSONValue

logger = get_logger(__name__)


def parse_sites(value: str) -> list[str] | None:
    """Parse a comma-separated list of site IDs or 'all' → None (meaning all)."""
    v = (value or "").strip()
    if not v or v == "all":
        return None
    return [s.strip() for s in v.split(",") if s.strip()]


async def existing_point_ids(
    *,
    qdrant_client: AsyncQdrantClient,
    collection: str,
    ids: list[str],
    chunk_size: int = 256,
) -> set[str]:
    """Return subset of ids that already exist in Qdrant.

    If the collection doesn't exist yet, returns an empty set.
    """
    if not ids:
        return set()

    existing: set[str] = set()

    for chunk in batched(ids, max(1, int(chunk_size)), strict=False):
        try:
            points = await qdrant_client.retrieve(
                collection_name=collection,
                ids=chunk,
                with_payload=False,
                with_vectors=False,
            )
        except Exception as exc:
            # Missing collection is a normal state pre-ingestion.
            msg = str(exc)
            if "doesn't exist" in msg or "Not found: Collection" in msg:
                return set()
            logger.warning(
                "Qdrant retrieve failed during existence check",
                collection=collection,
                error=msg,
                errorType=type(exc).__name__,
            )
            raise

        for p in points or []:
            existing.add(str(p.id))

    return existing


async def embed_and_upsert(
    *,
    store: QdrantStore,
    embedder: OpenAIEmbeddings,
    collection: str,
    ids: Sequence[str | JSONValue],
    texts: list[str],
    payloads: Sequence[JSONObject],
) -> None:
    """Embed *texts*, pair with *ids*/*payloads*, and upsert to *collection*.

    This is the shared core of both WDK and public-strategy indexing pipelines.
    """
    if not texts:
        return
    vectors = await embedder.embed_texts(texts)
    await store.upsert(
        collection=collection,
        points=[
            cast(
                "Any",
                {"id": pid, "vector": v, "payload": payload},
            )
            for pid, v, payload in zip(ids, vectors, payloads, strict=True)
        ],
    )
