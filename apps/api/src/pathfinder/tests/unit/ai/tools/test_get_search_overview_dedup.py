"""Read-only dedup for ``get_search_overview``.

Inspecting the same search twice in a turn is wasteful — the second call
returns an ``AlreadyReadNotice`` instead of re-dumping the full overview
and re-hitting WDK. The first read still registers the search in the
discovery gate so downstream tools (decision, params) keep working.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from pathfinder.ai.agents.state import AgentToolState
from pathfinder.ai.tools.standalone import _catalog_models, catalog_discovery
from pathfinder.ai.tools.standalone.catalog_discovery import AlreadyReadNotice
from pathfinder.integrations.veupathdb.wdk_parameters import WDKStringParam


def _ctx() -> Any:
    ctx = MagicMock()
    ctx.deps = MagicMock()
    ctx.deps.site_id = "plasmodb"
    ctx.deps.agent_state = AgentToolState()
    return ctx


def _wdk_param(name: str) -> WDKStringParam:
    return WDKStringParam(name=name, is_visible=True, allow_empty_value=False)


def _patch(monkeypatch: pytest.MonkeyPatch) -> Any:
    async def _resolve(*_args: Any, **_kw: Any) -> str:
        return "transcript"

    monkeypatch.setattr(catalog_discovery, "_resolve_record_type", _resolve)

    search_data = MagicMock()
    search_data.url_segment = "GenesByGoTerm"
    search_data.display_name = "Genes by GO Term"
    search_data.description = "Find genes by GO term"
    search_data.summary = "summary"
    search_data.parameters = [_wdk_param("go_term"), _wdk_param("taxon")]

    details = MagicMock()
    details.search_data = search_data

    client = MagicMock()
    client.get_search_details = AsyncMock(return_value=details)
    monkeypatch.setattr(_catalog_models, "get_wdk_client", lambda _site: client)

    def _overview(**_kw: Any) -> Any:
        return MagicMock()

    monkeypatch.setattr(catalog_discovery, "format_search_overview", _overview)
    return client


@pytest.mark.asyncio
async def test_first_read_registers_second_read_is_notice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _patch(monkeypatch)
    ctx = _ctx()

    first = await catalog_discovery.get_search_overview(
        ctx, search_name="GenesByGoTerm"
    )
    assert not isinstance(first, AlreadyReadNotice)
    assert ctx.deps.agent_state.get_overview("GenesByGoTerm") is not None
    assert client.get_search_details.await_count == 1

    second = await catalog_discovery.get_search_overview(
        ctx, search_name="GenesByGoTerm"
    )
    assert isinstance(second, AlreadyReadNotice)
    assert second.search_name == "GenesByGoTerm"
    # No second WDK round-trip on the repeat read.
    assert client.get_search_details.await_count == 1
