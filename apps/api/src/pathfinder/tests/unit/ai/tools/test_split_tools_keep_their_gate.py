"""The four split tools keep the discovery gate the service half does not hold.

Each tool reads through ``services/catalog`` and then writes the gate: the
catalog names the model may inspect, the registered search overview, the
parameter vocabulary snapshot, and the per-turn read ledger.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from pathfinder.ai.agents.state import AgentToolState, SearchOverview
from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.tools.standalone import catalog as catalog_tools
from pathfinder.ai.tools.standalone import catalog_discovery
from pathfinder.devtools.wdk_fixtures import load_recorded
from pathfinder.domain.parameters.values import SinglePickValue
from pathfinder.domain.strategy.session import StrategySession
from pathfinder.integrations.veupathdb.wdk_models import WDKSearchResponse
from pathfinder.services import catalog as catalog_service
from pathfinder.services.catalog import search_inspection, searches
from pathfinder.services.catalog.models import SearchMatch


def _ctx(state: AgentToolState, site_id: str = "plasmodb") -> Any:
    ctx = MagicMock()
    ctx.tool_call_id = "call_1"
    ctx.deps = AgentDeps(
        site_id=site_id,
        strategy_session=StrategySession(site_id=site_id),
        agent_state=state,
    )
    return ctx


def _inspected(name: str) -> SearchOverview:
    return SearchOverview(
        search_name=name,
        display_name=name,
        record_type="transcript",
        description="",
        parameter_names=[],
        required_params=[],
    )


def _stub_client(monkeypatch: pytest.MonkeyPatch, fixture: str) -> MagicMock:
    response = WDKSearchResponse.model_validate(load_recorded(fixture).json_body())
    client = MagicMock()
    client.get_search_details = AsyncMock(return_value=response)
    client.get_search_details_with_params = AsyncMock(return_value=response)
    monkeypatch.setattr(searches, "get_wdk_client", lambda _site: client)
    monkeypatch.setattr(search_inspection, "get_wdk_client", lambda _site: client)
    return client


class TestSearchForSearchesGate:
    async def test_it_records_every_name_it_returns(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        matches = [
            SearchMatch(
                name="GenesByTaxon",
                display_name="Genes by Taxon",
                description="Find genes by organism taxonomy",
                record_type="transcript",
                relevance=0.85,
            ),
            SearchMatch(
                name="GenesByGoTerm",
                display_name="Genes by GO Term",
                description="Find genes annotated with a GO term",
                record_type="transcript",
                relevance=0.5,
            ),
        ]

        async def _ranked(*_a: Any, **_k: Any) -> list[SearchMatch]:
            return matches

        monkeypatch.setattr(catalog_service, "search_for_searches", _ranked)
        state = AgentToolState()
        state.register_search("GenesByGoTerm", _inspected("GenesByGoTerm"))

        result = (
            await catalog_tools.search_for_searches(
                _ctx(state), query="gametocyte RNA-Seq differential expression"
            )
        ).return_value

        assert [row.get("name") for row in result] == [
            "GenesByTaxon",
            "GenesByGoTerm",
            "GenesByText",
        ]
        assert state.catalog_search_names == {
            "GenesByTaxon",
            "GenesByGoTerm",
            "GenesByText",
        }


class TestListSearchesGate:
    async def test_it_records_the_visible_names(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def _rows(*_a: Any, **_k: Any) -> list[dict[str, str]]:
            return [
                {"name": "GenesByTaxon", "displayName": "Genes by Taxon"},
                {"name": "GenesByGoTerm", "displayName": "Genes by GO Term"},
            ]

        monkeypatch.setattr(catalog_service, "list_searches", _rows)
        state = AgentToolState()
        state.register_search("GenesByGoTerm", _inspected("GenesByGoTerm"))

        result = (await catalog_tools.list_searches(_ctx(state))).return_value

        assert [row["name"] for row in result] == ["GenesByTaxon", "GenesByGoTerm"]
        assert state.catalog_search_names == {"GenesByTaxon", "GenesByGoTerm"}


class TestSearchOverviewGate:
    async def test_the_first_read_registers_the_search(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stub_client(monkeypatch, "search_genes_by_molecular_weight")
        state = AgentToolState()
        state.operational_spec_draft.goal = "kinase genes in the schizont stage"

        await catalog_discovery.get_search_overview(
            _ctx(state),
            search_name="GenesByMolecularWeight",
            record_type="transcript",
        )

        registered = state.get_overview("GenesByMolecularWeight")
        assert registered is not None
        assert registered.display_name == "Molecular Weight"
        assert registered.record_type == "transcript"
        assert registered.parameter_names == [
            "organism",
            "min_molecular_weight",
            "max_molecular_weight",
        ]
        assert registered.required_params == [
            "organism",
            "min_molecular_weight",
            "max_molecular_weight",
        ]

    async def test_the_draft_goal_ranks_the_sheet(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stub_client(monkeypatch, "search_genes_by_molecular_weight")
        captured: dict[str, str | None] = {}

        original = search_inspection.format_search_overview

        def _capture(**kwargs: Any) -> Any:
            captured["query"] = kwargs["query"]
            return original(**kwargs)

        monkeypatch.setattr(search_inspection, "format_search_overview", _capture)
        state = AgentToolState()
        state.operational_spec_draft.goal = "kinase genes in the schizont stage"

        await catalog_discovery.get_search_overview(
            _ctx(state),
            search_name="GenesByMolecularWeight",
            record_type="transcript",
        )

        assert captured["query"] == "kinase genes in the schizont stage"

    async def test_a_repeat_read_costs_no_wdk_call(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client = _stub_client(monkeypatch, "search_genes_by_molecular_weight")
        state = AgentToolState()
        ctx = _ctx(state)

        await catalog_discovery.get_search_overview(
            ctx, search_name="GenesByMolecularWeight", record_type="transcript"
        )
        repeat = (
            await catalog_discovery.get_search_overview(
                ctx, search_name="GenesByMolecularWeight", record_type="transcript"
            )
        ).return_value

        assert repeat.kind == "already_read"
        assert client.get_search_details.await_count == 1


class TestParameterOptionsGate:
    async def test_the_read_is_ledgered_and_the_vocabulary_snapshotted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stub_client(monkeypatch, "search_genes_by_location")
        state = AgentToolState()
        ctx = _ctx(state)
        await catalog_discovery.get_search_overview(
            ctx, search_name="GenesByLocation", record_type="transcript"
        )

        first = (
            await catalog_discovery.get_parameter_options(
                ctx,
                search_name="GenesByLocation",
                parameter_id="organismSinglePick",
                record_type="transcript",
            )
        ).return_value
        repeat = (
            await catalog_discovery.get_parameter_options(
                ctx,
                search_name="GenesByLocation",
                parameter_id="organismSinglePick",
                record_type="transcript",
            )
        ).return_value

        assert first.kind == "parameter_info"
        assert repeat.kind == "already_read"
        assert state.read_param_options == {"GenesByLocation|organismSinglePick||"}
        overview = state.get_overview("GenesByLocation")
        assert overview is not None
        assert "organismSinglePick" in overview.param_vocab

    async def test_bound_params_narrow_the_vocabulary_read(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client = _stub_client(monkeypatch, "search_genes_by_location")
        state = AgentToolState()
        captured: dict[str, Any] = {}

        def _bound(_search_name: str) -> dict[str, Any]:
            captured["asked"] = _search_name
            return {"organismSinglePick": SinglePickValue(value="P. falciparum 3D7")}

        monkeypatch.setattr(state, "resolved_params_for", _bound)

        result = (
            await catalog_discovery.get_parameter_options(
                _ctx(state),
                search_name="GenesByLocation",
                parameter_id="chromosomeOptional",
                record_type="transcript",
            )
        ).return_value

        assert result.kind == "parameter_info"
        assert captured["asked"] == "GenesByLocation"
        context = client.get_search_details_with_params.await_args.kwargs["context"]
        assert context["organismSinglePick"] == "P. falciparum 3D7"

    async def test_an_unknown_parameter_is_not_ledgered(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stub_client(monkeypatch, "search_genes_by_location")
        state = AgentToolState()

        result = (
            await catalog_discovery.get_parameter_options(
                _ctx(state),
                search_name="GenesByLocation",
                parameter_id="organism_single_pick",
                record_type="transcript",
            )
        ).return_value

        assert result.kind == "parameter_not_on_search"
        assert state.read_param_options == set()
