"""A vocabulary too large to travel whole is ranked against the user's goal.

The search description is the same text for every user who reads that search, so
it cannot separate the options one of them asked for.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from pathfinder.ai.agents.state import AgentToolState
from pathfinder.ai.tools.standalone import _catalog_models, catalog_discovery
from pathfinder.integrations.veupathdb.wdk_parameters import WDKStringParam

_GOAL = "kinase genes expressed in the schizont stage"


def _patch(monkeypatch: pytest.MonkeyPatch, captured: dict[str, str]) -> None:
    async def _resolve(*_a: Any, **_k: Any) -> str:
        return "transcript"

    monkeypatch.setattr(catalog_discovery, "_resolve_record_type", _resolve)

    search_data = MagicMock()
    search_data.url_segment = "GenesByGoTerm"
    search_data.display_name = "Genes by GO Term"
    search_data.description = "Find genes annotated with a GO term"
    search_data.summary = "summary"
    search_data.parameters = [WDKStringParam(name="go_term")]

    details = MagicMock()
    details.search_data = search_data

    client = MagicMock()
    client.get_search_details = AsyncMock(return_value=details)
    monkeypatch.setattr(_catalog_models, "get_wdk_client", lambda _site: client)

    def _overview(*, query: str, **_kw: Any) -> Any:
        captured["query"] = query
        return MagicMock()

    monkeypatch.setattr(catalog_discovery, "format_search_overview", _overview)


@pytest.mark.asyncio
async def test_the_sheet_is_ranked_on_the_goal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, str] = {}
    _patch(monkeypatch, captured)

    ctx = MagicMock()
    ctx.deps = MagicMock()
    ctx.deps.site_id = "plasmodb"
    ctx.deps.agent_state = AgentToolState()
    ctx.deps.agent_state.operational_spec_draft.goal = _GOAL

    await catalog_discovery.get_search_overview(ctx, search_name="GenesByGoTerm")

    assert captured["query"] == _GOAL
