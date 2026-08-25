"""``get_search_overview`` (used by the ``request_search_inspection`` escape
hatch) must hand the model a did-you-mean list when it names a search that
does not exist — otherwise the model loops on invented names until the
per-turn request limit."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic_ai.exceptions import ModelRetry

from pathfinder.ai.agents.state import AgentToolState
from pathfinder.ai.tools.standalone import catalog_discovery
from pathfinder.platform.errors import WDKError
from pathfinder.services.catalog import search_inspection, searches


def _ctx() -> Any:
    ctx = MagicMock()
    ctx.deps = MagicMock()
    ctx.deps.site_id = "vectorbase"
    ctx.deps.agent_state = AgentToolState()
    return ctx


def _search(name: str) -> Any:
    s = MagicMock()
    s.url_segment = name
    return s


@pytest.mark.asyncio
async def test_404_raises_model_retry_with_did_you_mean(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _resolve(*_a: Any, **_k: Any) -> str:
        return "transcript"

    monkeypatch.setattr(search_inspection, "resolve_search_record_type", _resolve)

    client = MagicMock()
    client.get_search_details = AsyncMock(
        side_effect=WDKError(
            "Resource 'search: GenesByText_Search' does not exist.", status=404
        )
    )
    monkeypatch.setattr(searches, "get_wdk_client", lambda _s: client)

    async def _valid(_site: str, _rt: str) -> list[Any]:
        return [_search("GenesByText"), _search("GenesByGoTerm")]

    monkeypatch.setattr(search_inspection, "get_raw_searches", _valid)

    ctx = _ctx()
    with pytest.raises(ModelRetry) as excinfo:
        await catalog_discovery.get_search_overview(
            ctx, search_name="GenesByText_Search"
        )

    msg = str(excinfo.value)
    assert "GenesByText" in msg
    assert "GenesByText_Search" in msg
    # The invented name must not be registered as a discovered search.
    assert ctx.deps.agent_state.get_overview("GenesByText_Search") is None


@pytest.mark.asyncio
async def test_non_404_wdk_error_propagates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _resolve(*_a: Any, **_k: Any) -> str:
        return "transcript"

    monkeypatch.setattr(search_inspection, "resolve_search_record_type", _resolve)

    client = MagicMock()
    client.get_search_details = AsyncMock(
        side_effect=WDKError("upstream 502", status=502)
    )
    monkeypatch.setattr(searches, "get_wdk_client", lambda _s: client)

    ctx = _ctx()
    with pytest.raises(WDKError):
        await catalog_discovery.get_search_overview(ctx, search_name="GenesByText")
