from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from pathfinder.ai.memory.retrieval import hybrid_score
from pathfinder.ai.memory.schemas import MemoryValue


def _m(tags: list[str], last_used_days_ago: float | None) -> MemoryValue:
    last_used = (
        datetime.now(UTC) - timedelta(days=last_used_days_ago)
        if last_used_days_ago is not None
        else None
    )
    return MemoryValue(
        kind="gene_set",
        name="x",
        summary="y",
        tags=tags,
        content={},
        created_at=datetime.now(UTC),
        last_used_at=last_used,
    )


def test_hybrid_score_combines_semantic_recency_pin() -> None:
    m = _m(tags=[], last_used_days_ago=0)
    score = hybrid_score(memory=m, semantic=1.0)
    # 0.7 * 1.0 + 0.2 * ~1.0 + 0.1 * 0 ~= 0.9
    assert 0.85 < score < 0.95


def test_recency_decay() -> None:
    fresh = hybrid_score(memory=_m(tags=[], last_used_days_ago=0), semantic=0.5)
    stale = hybrid_score(memory=_m(tags=[], last_used_days_ago=90), semantic=0.5)
    assert fresh > stale


def test_pinned_tag_boosts_score() -> None:
    unpinned = hybrid_score(memory=_m(tags=[], last_used_days_ago=30), semantic=0.5)
    pinned = hybrid_score(memory=_m(tags=["pinned"], last_used_days_ago=30), semantic=0.5)
    assert pinned > unpinned
    assert pinned - unpinned == pytest.approx(0.1, abs=0.01)
