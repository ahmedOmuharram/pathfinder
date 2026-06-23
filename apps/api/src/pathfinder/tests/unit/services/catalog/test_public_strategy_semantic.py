"""Semantic precedent ranking orders public strategies by embedding cosine, so a
goal phrased differently from a strategy ("immunization targets" vs "vaccine
antigens") still surfaces it — which lexical token overlap misses."""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from pathfinder.integrations.veupathdb.wdk_models import WDKStrategySummary
from pathfinder.services.catalog.public_strategy_search import (
    rank_public_strategies_semantic,
)


def _strat(sid: int, name: str, desc: str = "") -> WDKStrategySummary:
    return WDKStrategySummary(
        strategy_id=sid, name=name, root_step_id=sid, description=desc
    )


@pytest.mark.asyncio
async def test_ranks_by_cosine_similarity() -> None:
    strategies = [_strat(1, "A"), _strat(2, "B"), _strat(3, "C")]

    async def fake_embed(texts: Sequence[str]) -> list[list[float]]:
        assert texts[0].startswith("search_query:")
        return [[1.0, 0.0], [1.0, 0.0], [0.0, 1.0], [0.7, 0.7]]

    out = await rank_public_strategies_semantic(
        strategies, "q", embed=fake_embed, limit=3, min_score=-1.0
    )
    assert [r["name"] for r in out] == ["A", "C", "B"]


@pytest.mark.asyncio
async def test_below_threshold_dropped() -> None:
    strategies = [_strat(1, "A"), _strat(2, "B")]

    async def fake_embed(_texts: Sequence[str]) -> list[list[float]]:
        return [[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]]  # B orthogonal -> cosine 0

    out = await rank_public_strategies_semantic(
        strategies, "q", embed=fake_embed, limit=3, min_score=0.4
    )
    assert [r["name"] for r in out] == ["A"]


@pytest.mark.asyncio
async def test_empty_inputs_return_empty() -> None:
    async def fake_embed(_texts: Sequence[str]) -> list[list[float]]:
        return [[1.0]]

    assert await rank_public_strategies_semantic([], "q", embed=fake_embed) == []
    assert (
        await rank_public_strategies_semantic([_strat(1, "A")], "   ", embed=fake_embed)
        == []
    )
