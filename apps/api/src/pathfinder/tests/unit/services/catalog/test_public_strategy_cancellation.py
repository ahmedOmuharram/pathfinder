"""A caller that walks away from precedent ranking stops the embedding work.

The pass embeds every public strategy of a site. One call that embeds the whole
list holds every vector at once and observes no cancellation, so an abandoned
call runs to the end inside the server's memory ceiling.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

import pytest

from pathfinder.integrations.veupathdb.wdk_models import WDKStrategySummary
from pathfinder.services.catalog.public_strategy_search import (
    EMBED_BATCH,
    rank_public_strategies_semantic,
)


def _strategies(count: int) -> list[WDKStrategySummary]:
    return [
        WDKStrategySummary(strategy_id=i, name=f"S{i}", root_step_id=i)
        for i in range(count)
    ]


async def test_no_call_carries_more_texts_than_one_batch() -> None:
    sizes: list[int] = []

    async def fake_embed(texts: Sequence[str]) -> list[list[float]]:
        sizes.append(len(texts))
        return [[1.0, 0.0] for _ in texts]

    await rank_public_strategies_semantic(
        _strategies(EMBED_BATCH * 3 + 1),
        "q",
        embed=fake_embed,
        min_score=-1.0,
    )

    assert max(sizes) <= EMBED_BATCH
    assert sum(sizes) == EMBED_BATCH * 3 + 2


async def test_a_cancelled_caller_stops_before_the_next_batch() -> None:
    entered = asyncio.Event()
    release = asyncio.Event()
    calls: list[int] = []

    async def fake_embed(texts: Sequence[str]) -> list[list[float]]:
        calls.append(len(texts))
        if len(calls) == 2:
            entered.set()
            await release.wait()
        return [[1.0, 0.0] for _ in texts]

    task = asyncio.create_task(
        rank_public_strategies_semantic(
            _strategies(EMBED_BATCH * 4),
            "q",
            embed=fake_embed,
            min_score=-1.0,
        )
    )
    await entered.wait()
    task.cancel()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    await asyncio.sleep(0)

    assert len(calls) == 2
