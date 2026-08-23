from __future__ import annotations

import asyncio
import math
from collections.abc import Sequence

from assistant_core.embeddings.model import get_embedding_model
from assistant_core.embeddings.prefixes import SEARCH_DOCUMENT_PREFIX
from assistant_core.memory.schemas import MemoryValue

MEMORY_EMBEDDING_MODEL: str = "nomic-ai/nomic-embed-text-v1.5"
EMBEDDING_DIMENSIONS: int = 512


def _truncate_matryoshka(vector: list[float]) -> list[float]:
    """Matryoshka-truncate 768->512 and L2-renormalize.

    The L2 renormalization is load-bearing: downstream, the LangGraph store
    computes cosine similarity as ``1 - (vector <=> query)``. Pgvector's
    ``<=>`` returns a value in ``[0, 2]`` for arbitrary vectors, which
    would make the stored ``Item.score`` fall outside ``[0, 1]``. With
    both query and stored vectors L2-normalized here, the cosine distance
    is bounded to ``[0, 2]`` with 0 indicating identical direction and 1
    indicating orthogonality, so ``score = 1 - distance`` lands cleanly
    in ``[-1, 1]`` and clusters in ``[0, 1]`` for semantically related
    text. ``retrieval._clamp_semantic`` depends on this invariant.
    """
    truncated = vector[:EMBEDDING_DIMENSIONS]
    norm = math.sqrt(sum(x * x for x in truncated))
    if norm == 0:
        return truncated
    return [x / norm for x in truncated]


async def embed_text(texts: Sequence[str]) -> list[list[float]]:
    """Async-friendly embedding. Offloads CPU-bound work to a thread.

    LangGraph's :class:`AsyncPostgresStore` calls this once per configured
    ``fields`` entry per item. We point ``fields`` at a single synthetic
    payload key (``_embed_text``) so every memory gets exactly one
    embedding — see :func:`format_embedded_string` for the text shape.
    """

    def _run() -> list[list[float]]:
        raw_vectors = list(get_embedding_model().embed(list(texts)))
        return [_truncate_matryoshka(list(map(float, v))) for v in raw_vectors]

    return await asyncio.to_thread(_run)


def format_embedded_string(value: MemoryValue) -> str:
    """Combined text used for a memory's embedding.

    LangGraph's ``fields`` config points at one payload key; every field
    listed there causes a separate embedding per put. To get semantic
    match on kind + name + tags + summary with a single embedding, we
    concatenate them into this string and store it under ``_embed_text``
    in the payload — the store indexes that one key.
    """
    tags_joined = ", ".join(value.tags)
    return (
        f"{SEARCH_DOCUMENT_PREFIX}{value.kind} :: {value.name} :: "
        f"{tags_joined} :: {value.summary}"
    )
