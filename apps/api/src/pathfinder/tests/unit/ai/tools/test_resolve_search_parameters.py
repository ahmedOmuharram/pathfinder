"""``resolve_search_parameters`` resolves and snapshots the vocabulary for
every REQUIRED param of a selected search in one call — so planning copies
validated values instead of guessing (the GenesByGoTerm go_term_evidence=EXP
thrash). It reuses the same WDK fetch + format_typed_param + _snapshot_param_vocab
machinery as get_parameter_options, looped over the required params.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic_ai.exceptions import ModelRetry

from pathfinder.ai.agents.state import AgentToolState, SearchOverview
from pathfinder.ai.tools.standalone import catalog_discovery
from pathfinder.domain.parameters.wdk_vocab import VocabOption
from pathfinder.services.catalog.param_formatting import ParameterInfo


def _ctx_with_state(state: AgentToolState) -> Any:
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


def _go_search() -> SearchOverview:
    return SearchOverview(
        search_name="GenesByGoTerm",
        display_name="GO term",
        record_type="transcript",
        description="",
        parameter_names=["organism", "go_typeahead", "go_term", "go_term_evidence"],
        required_params=["organism", "go_term", "go_term_evidence"],
    )


_INFO: dict[str, ParameterInfo] = {
    "organism": ParameterInfo(
        name="organism",
        display_name="organism",
        type="multi-pick-vocabulary",
        required=True,
        is_visible=True,
        help="organisms",
        value_format='{"type": "multi-pick-vocabulary"}',
        default_value=None,
        allowed_values_tree="Plasmodium\n  P. falciparum 3D7",
    ),
    "go_term": ParameterInfo(
        name="go_term",
        display_name="GO term",
        type="string",
        required=True,
        is_visible=True,
        help="legacy widget; use N/A",
        value_format='{"type": "string"}',
        default_value="N/A",
    ),
    "go_term_evidence": ParameterInfo(
        name="go_term_evidence",
        display_name="Evidence",
        type="multi-pick-vocabulary",
        required=True,
        is_visible=True,
        help="evidence class",
        value_format='{"type": "multi-pick-vocabulary"}',
        default_value=None,
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

    fake_details = MagicMock()
    fake_details.search_data.parameters = [
        _wdk_param(n)
        for n in ("organism", "go_typeahead", "go_term", "go_term_evidence")
    ]
    client = MagicMock()
    client.get_search_details = AsyncMock(return_value=fake_details)
    monkeypatch.setattr(catalog_discovery, "get_wdk_client", lambda _s: client)
    monkeypatch.setattr(
        catalog_discovery,
        "format_typed_param",
        lambda p, **_k: _INFO[p.name],
    )


@pytest.mark.asyncio
async def test_resolve_snapshots_all_required_params(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = AgentToolState()
    state.register_search("GenesByGoTerm", _go_search())
    _patch(monkeypatch)

    await catalog_discovery.resolve_search_parameters(
        _ctx_with_state(state), search_name="GenesByGoTerm"
    )

    overview = state.get_overview("GenesByGoTerm")
    assert overview is not None
    # Every required param is now snapshotted (not just the one queried earlier).
    assert {"organism", "go_term", "go_term_evidence"} <= set(overview.param_vocab)
    ev = overview.param_vocab["go_term_evidence"]
    assert ev.allowed_values is not None
    assert [v.value for v in ev.allowed_values] == ["Curated", "Computed"]


@pytest.mark.asyncio
async def test_resolve_result_lists_accepted_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = AgentToolState()
    state.register_search("GenesByGoTerm", _go_search())
    _patch(monkeypatch)

    result = await catalog_discovery.resolve_search_parameters(
        _ctx_with_state(state), search_name="GenesByGoTerm"
    )
    blob = result.model_dump_json()
    assert "go_term_evidence" in blob
    assert "Curated" in blob
    assert "Computed" in blob


@pytest.mark.asyncio
async def test_resolve_requires_prior_inspection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = AgentToolState()  # nothing inspected
    _patch(monkeypatch)
    with pytest.raises(ModelRetry):
        await catalog_discovery.resolve_search_parameters(
            _ctx_with_state(state), search_name="GenesByGoTerm"
        )
