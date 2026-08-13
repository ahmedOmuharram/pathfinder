"""Embeddings retrieve; they must never decide.

The portal's `GenesByInterproDomain.domain_typeahead` has 12,113 entries, about
219K tokens. The whole vocabulary can never be sent to a model, and paginating it
across three 100K calls for one parameter costs more than the problem is worth.

So embeddings rank the options against the criterion text and only the top slice
travels. That is a *recall* job: if the right option misses the shortlist the
resolver answers "not determinable" and a question is asked, which is safe.
Letting the same embeddings *pick* is what bound `PF00069` to
`IPR000023 : Phosphofructokinase_dom` -- far fewer genes than intended, verification
green.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from pathfinder.domain.parameters.wdk_vocab import VocabOption
from pathfinder.services.catalog.vocab_narrowing import (
    DIRECT_MAX,
    TOP_K,
    narrow_candidates,
)


def _options(n: int) -> list[VocabOption]:
    return [VocabOption(value=f"IPR{i:06}", display=f"domain {i}") for i in range(n)]


def _embed_ranking(order: dict[str, float]):
    """Fake embeddings: the query is [1,0]; each option's vector encodes the
    similarity we want it to score, so ranking is exact and deterministic."""

    async def embed(texts: Sequence[str]) -> list[list[float]]:
        vectors = [[1.0, 0.0]]
        for text in list(texts)[1:]:
            score = next((s for k, s in order.items() if k in text), 0.0)
            vectors.append([score, 0.0])
        return vectors

    return embed


class TestSmallVocabulariesTravelWhole:
    @pytest.mark.asyncio
    async def test_a_small_vocabulary_is_not_narrowed(self) -> None:
        options = _options(10)

        narrowed = await narrow_candidates(
            options, "kinase domain", embed=_embed_ranking({})
        )

        assert narrowed == options

    @pytest.mark.asyncio
    async def test_the_boundary_is_inclusive(self) -> None:
        options = _options(DIRECT_MAX)

        narrowed = await narrow_candidates(options, "kinase", embed=_embed_ranking({}))

        assert len(narrowed) == DIRECT_MAX

    @pytest.mark.asyncio
    async def test_an_empty_vocabulary_stays_empty(self) -> None:
        assert await narrow_candidates([], "kinase", embed=_embed_ranking({})) == []


class TestLargeVocabulariesAreRanked:
    @pytest.mark.asyncio
    async def test_only_the_top_slice_travels(self) -> None:
        narrowed = await narrow_candidates(
            _options(DIRECT_MAX + 500), "kinase", embed=_embed_ranking({})
        )

        assert len(narrowed) == TOP_K

    @pytest.mark.asyncio
    async def test_the_best_match_survives_narrowing(self) -> None:
        # The one entry the criterion actually names must not be ranked away --
        # this is the recall property the whole design rests on.
        options = [
            *_options(DIRECT_MAX + 500),
            VocabOption(value="PF00069", display="Pkinase"),
        ]

        narrowed = await narrow_candidates(
            options, "protein kinase PF00069", embed=_embed_ranking({"Pkinase": 1.0})
        )

        assert any(o.value == "PF00069" for o in narrowed)

    @pytest.mark.asyncio
    async def test_ranking_puts_the_best_match_first(self) -> None:
        options = [
            *_options(DIRECT_MAX + 100),
            VocabOption(value="PF00069", display="Pkinase"),
        ]

        narrowed = await narrow_candidates(
            options, "protein kinase", embed=_embed_ranking({"Pkinase": 1.0})
        )

        assert narrowed[0].value == "PF00069"


class TestExactMatchesAreNeverRankedAway:
    @pytest.mark.asyncio
    async def test_a_value_named_verbatim_is_always_kept(self) -> None:
        # An identifier written in the request is not a similarity question. If
        # embeddings rank it 12,000th it must still travel, or the resolver is
        # asked to choose from a shortlist that excludes the right answer.
        options = [
            *_options(DIRECT_MAX + 500),
            VocabOption(value="PF00069", display="Pkinase"),
        ]

        narrowed = await narrow_candidates(
            options, "domain PF00069", embed=_embed_ranking({})
        )

        assert any(o.value == "PF00069" for o in narrowed)

    @pytest.mark.asyncio
    async def test_the_shortlist_still_respects_the_cap(self) -> None:
        options = [
            *_options(DIRECT_MAX + 500),
            VocabOption(value="PF00069", display="Pkinase"),
        ]

        narrowed = await narrow_candidates(
            options, "domain PF00069", embed=_embed_ranking({})
        )

        assert len(narrowed) <= TOP_K
