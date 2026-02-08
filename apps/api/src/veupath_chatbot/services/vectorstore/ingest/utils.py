from __future__ import annotations

from collections.abc import Iterable
from typing import TypeVar

from qdrant_client import AsyncQdrantClient

from veupath_chatbot.platform.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


def chunks[T](items: list[T], *, size: int) -> Iterable[list[T]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


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

    for chunk in chunks(ids, size=max(1, int(chunk_size))):
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
