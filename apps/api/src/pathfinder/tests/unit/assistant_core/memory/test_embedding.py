from __future__ import annotations

import math
from datetime import UTC, datetime

import pytest

from pathfinder.assistant_core.memory.embedding import (
    EMBEDDING_DIMENSIONS,
    MEMORY_EMBEDDING_MODEL,
    embed_text,
    format_embedded_string,
)
from pathfinder.assistant_core.memory.schemas import MemoryValue
from pathfinder.integrations.embeddings.prefixes import SEARCH_DOCUMENT_PREFIX


def test_embedding_dimensions_are_512() -> None:
    assert EMBEDDING_DIMENSIONS == 512


def test_model_name_is_nomic_512() -> None:
    assert "nomic" in MEMORY_EMBEDDING_MODEL.lower()


@pytest.mark.asyncio
async def test_embed_text_returns_512_float_vector() -> None:
    vectors = await embed_text(["a simple test sentence"])
    assert len(vectors) == 1
    assert len(vectors[0]) == 512
    for x in vectors[0]:
        assert isinstance(x, float)


@pytest.mark.asyncio
async def test_embed_multiple_strings() -> None:
    vectors = await embed_text(["hello", "world", "foo bar"])
    assert len(vectors) == 3
    for v in vectors:
        assert len(v) == 512


@pytest.mark.asyncio
async def test_similar_strings_have_higher_cosine_than_dissimilar() -> None:
    def cos(u: list[float], v: list[float]) -> float:
        dot = sum(a * b for a, b in zip(u, v, strict=True))
        nu = math.sqrt(sum(a * a for a in u))
        nv = math.sqrt(sum(a * a for a in v))
        return dot / (nu * nv)

    vectors = await embed_text(
        [
            "plasmodium falciparum drug target genes",
            "falciparum antimalarial targets",
            "a recipe for chocolate chip cookies",
        ]
    )
    similar = cos(vectors[0], vectors[1])
    unrelated = cos(vectors[0], vectors[2])
    assert similar > unrelated


@pytest.mark.asyncio
async def test_embed_text_returns_l2_normalized_vectors() -> None:
    """Invariant guarded by retrieval._clamp_semantic.

    ``embed_text`` Matryoshka-truncates + L2-renormalizes. Dropping this
    renormalization would move pgvector's cosine-distance-derived scores
    outside ``[0, 1]`` and silently break retrieval's hybrid scoring.
    This test will fail LOUDLY on regression.
    """
    vectors = await embed_text(["norm check"])
    assert len(vectors) == 1
    norm_sq = sum(x * x for x in vectors[0])
    assert abs(norm_sq - 1.0) < 1e-5, (
        f"embed_text must L2-normalize; got norm^2 = {norm_sq}"
    )


def test_format_embedded_string_carries_nomic_document_prefix() -> None:
    """Stored memories are documents in nomic's asymmetric retrieval scheme.

    Without the ``search_document:`` prefix the stored vectors live in a
    different space than ``search_query:``-prefixed queries, degrading recall.
    """
    value = MemoryValue(
        kind="gene_set",
        name="vaccine_antigens",
        summary="surface-exposed blood-stage antigens",
        tags=["malaria", "vaccine"],
        content={},
        created_at=datetime.now(UTC),
    )
    text = format_embedded_string(value)
    assert text.startswith(SEARCH_DOCUMENT_PREFIX)
    # The semantic payload (kind/name/tags/summary) survives the prefix.
    assert "gene_set" in text
    assert "vaccine_antigens" in text
    assert "surface-exposed blood-stage antigens" in text
    assert "malaria" in text
