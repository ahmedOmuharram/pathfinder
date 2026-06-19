"""The Lead's compare_variants_scored tool: fetch the control set, run the
scored comparison, and emit a data-scored-comparison card."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from pydantic_ai.exceptions import ModelRetry

from pathfinder.ai.tools.standalone import scored_comparison as tool_mod
from pathfinder.ai.tools.standalone.scored_comparison import compare_variants_scored
from pathfinder.services.experiment.scored_comparison import (
    ScoredComparison,
    ScoredVariant,
)
from pathfinder.services.experiment.variant_comparison import VariantSpec


class _SessionCM:
    async def __aenter__(self) -> Any:
        return MagicMock()

    async def __aexit__(self, *_a: Any) -> bool:
        return False


def _ctx() -> Any:
    ctx = MagicMock()
    ctx.deps = MagicMock()
    ctx.deps.runtime.site_id = "plasmodb"
    ctx.deps.runtime.user_id = uuid4()
    ctx.deps.runtime.db_session_factory = MagicMock(return_value=_SessionCM())
    return ctx


def _variants() -> list[VariantSpec]:
    return [
        VariantSpec(label="a", search_name="SA", parameters={}),
        VariantSpec(label="b", search_name="SB", parameters={}),
    ]


@pytest.mark.asyncio
async def test_emits_scored_card_and_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    control_set = MagicMock()
    control_set.positive_ids = ["g1", "g2"]
    control_set.negative_ids = ["n1"]
    service = MagicMock()
    service.get = AsyncMock(return_value=control_set)
    monkeypatch.setattr(tool_mod, "ControlSetService", lambda _s: service)

    comparison = ScoredComparison(
        variants=[
            ScoredVariant(label="a", search_name="SA", mcc=0.6, f1=0.8, precision=0.8),
            ScoredVariant(label="b", search_name="SB", mcc=0.9, f1=0.9, precision=0.9),
        ],
        winner_label="b",
        objective="mcc",
    )
    captured: dict[str, Any] = {}

    async def _run(
        site_id: str, user_id: str | None, variants: Any, **kw: Any
    ) -> ScoredComparison:
        captured["positive"] = kw["positive_controls"]
        captured["objective"] = kw["objective"]
        return comparison

    monkeypatch.setattr(tool_mod, "run_scored_comparison", _run)

    result = await compare_variants_scored(
        _ctx(), _variants(), control_set_id=str(uuid4()), objective="mcc"
    )

    assert result.return_value.winner_label == "b"
    assert captured["positive"] == ["g1", "g2"]
    chunk = result.metadata[0]
    assert chunk.type == "data-scored-comparison"
    assert "Winner: b" in (result.content or "")


@pytest.mark.asyncio
async def test_refuses_single_variant(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tool_mod, "ControlSetService", lambda _s: MagicMock())
    with pytest.raises(ModelRetry, match="at least 2"):
        await compare_variants_scored(
            _ctx(),
            [VariantSpec(label="a", search_name="SA", parameters={})],
            control_set_id=str(uuid4()),
        )
