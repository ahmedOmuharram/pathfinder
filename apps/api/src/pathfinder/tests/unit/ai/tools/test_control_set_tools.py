"""Lead control-set tools: validate IDs against WDK and persist a ControlSet,
report unresolved IDs, refuse when no positive control resolves, and list
existing sets.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from pydantic_ai.exceptions import ModelRetry

from pathfinder.ai.tools.standalone import control_sets
from pathfinder.ai.tools.standalone.control_sets import (
    build_control_set,
    list_control_sets,
)
from pathfinder.services.experiment.control_sourcing import ResolvedControls


class _SessionCM:
    def __init__(self) -> None:
        self.session = MagicMock()
        self.session.commit = AsyncMock()

    async def __aenter__(self) -> Any:
        return self.session

    async def __aexit__(self, *_a: Any) -> bool:
        return False


def _ctx() -> Any:
    ctx = MagicMock()
    ctx.tool_call_id = "call_1"
    ctx.deps = MagicMock()
    ctx.deps.runtime.site_id = "plasmodb"
    ctx.deps.runtime.user_id = uuid4()
    ctx.deps.runtime.db_session_factory = MagicMock(return_value=_SessionCM())
    return ctx


def _patch_validate(
    monkeypatch: pytest.MonkeyPatch, results: dict[str, ResolvedControls]
) -> None:
    async def _v(site_id: str, gene_ids: list[str], **_kw: Any) -> ResolvedControls:
        key = ",".join(gene_ids)
        return results.get(key, ResolvedControls())

    monkeypatch.setattr(control_sets, "validate_control_ids", _v)


@pytest.mark.asyncio
async def test_build_control_set_validates_persists_and_reports_unresolved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_validate(
        monkeypatch,
        {
            "g1,typo,g2": ResolvedControls(
                valid_ids=["g1", "g2"], unresolved_ids=["typo"]
            ),
            "n1": ResolvedControls(valid_ids=["n1"], unresolved_ids=[]),
        },
    )
    created = MagicMock()
    created.id = "cs_123"
    created.name = "my controls"
    service = MagicMock()
    service.create = AsyncMock(return_value=created)
    monkeypatch.setattr(control_sets, "ControlSetService", lambda _s: service)

    out = (
        await build_control_set(
            _ctx(),
            name="my controls",
            positive_ids=["g1", "typo", "g2"],
            negative_ids=["n1"],
        )
    ).return_value

    assert out.control_set_id == "cs_123"
    assert out.positive_count == 2
    assert out.negative_count == 1
    assert out.unresolved_positive == ["typo"]
    service.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_build_control_set_refuses_when_no_positive_resolves(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_validate(
        monkeypatch,
        {"bad1,bad2": ResolvedControls(valid_ids=[], unresolved_ids=["bad1", "bad2"])},
    )
    monkeypatch.setattr(control_sets, "ControlSetService", lambda _s: MagicMock())

    with pytest.raises(ModelRetry, match="No positive control"):
        await build_control_set(_ctx(), name="x", positive_ids=["bad1", "bad2"])


@pytest.mark.asyncio
async def test_list_control_sets_summarizes(monkeypatch: pytest.MonkeyPatch) -> None:
    cs = MagicMock()
    cs.id = "cs_1"
    cs.name = "set"
    cs.positive_ids = ["g1", "g2"]
    cs.negative_ids = ["n1"]
    service = MagicMock()
    service.list_for_site = AsyncMock(return_value=[cs])
    monkeypatch.setattr(control_sets, "ControlSetService", lambda _s: service)

    out = (await list_control_sets(_ctx())).return_value
    assert len(out) == 1
    assert out[0].control_set_id == "cs_1"
    assert out[0].positive_count == 2
    assert out[0].negative_count == 1
