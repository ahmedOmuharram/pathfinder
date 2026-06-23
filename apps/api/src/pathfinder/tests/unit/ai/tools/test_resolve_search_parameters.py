"""``resolve_search_parameters`` delegates to the DAG resolver, snapshots every
required param's (context-refreshed) vocab, and returns accepted values plus the
Tier-1 ``resolved_value`` — so planning copies validated values instead of
guessing. The inspection guard is unchanged."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from pydantic_ai.exceptions import ModelRetry

from pathfinder.ai.agents.state import AgentToolState, SearchOverview
from pathfinder.ai.tools.standalone import catalog_discovery
from pathfinder.domain.parameters.wdk_vocab import VocabOption
from pathfinder.services.catalog.param_dag import AutoResolved, DagResolution
from pathfinder.services.catalog.param_formatting import ParameterInfo


def _ctx_with_state(state: AgentToolState) -> Any:
    ctx = MagicMock()
    ctx.deps = MagicMock()
    ctx.deps.site_id = "plasmodb"
    ctx.deps.agent_state = state
    return ctx


def _go_search() -> SearchOverview:
    return SearchOverview(
        search_name="GenesByGoTerm",
        display_name="GO term",
        record_type="transcript",
        description="",
        parameter_names=["organism", "go_typeahead", "go_term", "go_term_evidence"],
        required_params=["organism", "go_term", "go_term_evidence"],
    )


def _pinfo(
    name: str,
    ptype: str,
    *,
    allowed: list[VocabOption] | None = None,
    tree: str | None = None,
    default: str | None = None,
) -> ParameterInfo:
    return ParameterInfo(
        name=name,
        display_name=name,
        type=ptype,
        required=True,
        is_visible=True,
        help=f"{name} help",
        value_format="",
        default_value=default,
        allowed_values=allowed,
        allowed_values_tree=tree,
    )


_RESOLUTION = DagResolution(
    auto_resolved=[AutoResolved(name="go_term", value="N/A")],
    param_infos=[
        _pinfo("organism", "multi-pick-vocabulary", tree="Plasmodium\n  P. falciparum"),
        _pinfo(
            "go_term",
            "string",
            allowed=[VocabOption(value="N/A", display="N/A")],
            default="N/A",
        ),
        _pinfo(
            "go_term_evidence",
            "multi-pick-vocabulary",
            allowed=[
                VocabOption(value="Curated", display="Curated"),
                VocabOption(value="Computed", display="Computed"),
            ],
        ),
    ],
)


def _patch(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _resolve_rt(*_a: Any, **_k: Any) -> str:
        return "transcript"

    async def _resolver(**_k: Any) -> DagResolution:
        return _RESOLUTION

    monkeypatch.setattr(catalog_discovery, "_resolve_record_type", _resolve_rt)
    monkeypatch.setattr(catalog_discovery, "resolve_parameter_dag", _resolver)


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
    assert {"organism", "go_term", "go_term_evidence"} <= set(overview.param_vocab)
    ev = overview.param_vocab["go_term_evidence"]
    assert ev.allowed_values is not None
    assert [v.value for v in ev.allowed_values] == ["Curated", "Computed"]


@pytest.mark.asyncio
async def test_resolve_result_lists_accepted_and_resolved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = AgentToolState()
    state.register_search("GenesByGoTerm", _go_search())
    _patch(monkeypatch)

    result = await catalog_discovery.resolve_search_parameters(
        _ctx_with_state(state), search_name="GenesByGoTerm"
    )

    blob = result.model_dump_json()
    assert "Curated" in blob
    assert "Computed" in blob
    go_term = next(p for p in result.params if p.name == "go_term")
    assert go_term.resolved_value == "N/A"


@pytest.mark.asyncio
async def test_resolve_requires_prior_inspection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = AgentToolState()
    _patch(monkeypatch)
    with pytest.raises(ModelRetry):
        await catalog_discovery.resolve_search_parameters(
            _ctx_with_state(state), search_name="GenesByGoTerm"
        )
