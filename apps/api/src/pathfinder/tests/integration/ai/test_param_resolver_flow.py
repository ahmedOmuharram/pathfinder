"""Discovery selection contract: resolve_search_parameters and the
update_search_decision guard COMPOSE on shared state — selecting a search is
blocked until the resolver has snapshotted its required params, then allowed.

Exercises the real tool functions over a real AgentToolState; only the WDK
fetch is mocked (the LLM-free boundary).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic_ai.exceptions import ModelRetry

from pathfinder.ai.agents.state import AgentToolState, SearchOverview
from pathfinder.ai.tools.standalone import catalog_discovery, catalog_selection
from pathfinder.domain.parameters.wdk_vocab import VocabOption
from pathfinder.services.catalog.param_formatting import ParameterInfo

pytestmark = pytest.mark.asyncio


def _ctx(state: AgentToolState) -> Any:
    ctx = MagicMock()
    ctx.deps = MagicMock()
    ctx.deps.site_id = "plasmodb"
    ctx.deps.agent_state = state
    return ctx


def _wdk_param(name: str) -> Any:
    p = MagicMock()
    p.name = name
    p.dependent_params = []
    return p


def _overview() -> SearchOverview:
    return SearchOverview(
        search_name="GenesByGoTerm",
        display_name="GO term",
        record_type="transcript",
        description="",
        parameter_names=["go_term", "go_term_evidence"],
        required_params=["go_term", "go_term_evidence"],
    )


_INFO = {
    "go_term": ParameterInfo(
        name="go_term",
        display_name="GO term",
        type="string",
        required=True,
        is_visible=True,
        help="legacy widget",
        value_format='{"type": "string"}',
        default_value="N/A",
    ),
    "go_term_evidence": ParameterInfo(
        name="go_term_evidence",
        display_name="Evidence",
        type="multi-pick-vocabulary",
        required=True,
        is_visible=True,
        help="evidence",
        value_format='{"type": "multi-pick-vocabulary"}',
        allowed_values=[
            VocabOption(value="Curated", display="Curated"),
            VocabOption(value="Computed", display="Computed"),
        ],
    ),
}


def _patch(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _resolve(*_a: Any, **_k: Any) -> str:
        return "transcript"

    monkeypatch.setattr(catalog_discovery, "_resolve_record_type", _resolve)
    fake = MagicMock()
    fake.search_data.parameters = [
        _wdk_param("go_term"),
        _wdk_param("go_term_evidence"),
    ]
    client = MagicMock()
    client.get_search_details = AsyncMock(return_value=fake)
    monkeypatch.setattr(catalog_discovery, "get_wdk_client", lambda _s: client)
    monkeypatch.setattr(
        catalog_discovery, "format_typed_param", lambda p, **_k: _INFO[p.name]
    )


async def test_select_blocked_then_allowed_after_resolve(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = AgentToolState()
    state.register_search("GenesByGoTerm", _overview())
    _patch(monkeypatch)
    ctx = _ctx(state)

    # Selecting before resolving is refused, naming the resolver.
    with pytest.raises(ModelRetry) as exc:
        await catalog_selection.update_search_decision(
            ctx,
            search_name="GenesByGoTerm",
            selection_status="selected",
            rationale="anchor",
            confidence=0.9,
        )
    assert "resolve_search_parameters" in str(exc.value)

    # Resolve, then selection succeeds.
    await catalog_discovery.resolve_search_parameters(ctx, search_name="GenesByGoTerm")
    result = await catalog_selection.update_search_decision(
        ctx,
        search_name="GenesByGoTerm",
        selection_status="selected",
        rationale="anchor",
        confidence=0.9,
        param_hints={"go_term": "N/A", "go_term_evidence": ["Curated", "Computed"]},
    )
    assert isinstance(result, str)
    stored = state.get_overview("GenesByGoTerm")
    assert stored is not None
    assert stored.selection_status == "selected"
    assert {"go_term", "go_term_evidence"} <= set(stored.param_vocab)
