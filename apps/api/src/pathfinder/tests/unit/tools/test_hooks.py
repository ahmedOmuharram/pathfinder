"""Tests for pydantic-ai lifecycle hooks."""

import json

from pathfinder.ai.agents._hooks import (
    _slim_graph_result,
    _track_search_discovery,
)
from pathfinder.ai.agents.state import AgentToolState
from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.domain.strategy.ast import PlanStepNode
from pathfinder.domain.strategy.session import StrategyGraph, StrategySession
from pathfinder.services.strategies.sync_state import WDKSyncState


def _make_deps(site_id: str = "plasmodb") -> AgentDeps:
    session = StrategySession(site_id=site_id)
    return AgentDeps(
        site_id=site_id,
        strategy_session=session,
        agent_state=AgentToolState(),
    )


def test_discovery_tracking_registers_search() -> None:
    deps = _make_deps()
    result_text = json.dumps({
        "searchName": "GenesByTaxon",
        "displayName": "Genes by Taxon",
        "recordType": "transcript",
        "description": "Find genes by organism taxonomy",
        "required": [
            {"name": "organism", "type": "string"},
            {"name": "min_expr", "type": "number"},
        ],
        "optional": [
            {"name": "max_pvalue", "type": "number"},
        ],
    })

    _track_search_discovery(deps, result_text)

    assert deps.agent_state.is_search_discovered("GenesByTaxon")
    overview = deps.agent_state.get_overview("GenesByTaxon")
    assert overview is not None
    assert overview.search_name == "GenesByTaxon"
    assert overview.display_name == "Genes by Taxon"
    assert overview.record_type == "transcript"
    assert overview.description == "Find genes by organism taxonomy"
    assert overview.required_params == ["organism", "min_expr"]
    assert overview.parameter_names == ["organism", "min_expr", "max_pvalue"]


def test_discovery_tracking_ignores_empty_search_name() -> None:
    deps = _make_deps()
    result_text = json.dumps({
        "searchName": "",
        "displayName": "Empty",
    })

    _track_search_discovery(deps, result_text)

    assert len(deps.agent_state.discovered_searches) == 0


def test_discovery_tracking_ignores_invalid_json() -> None:
    deps = _make_deps()

    _track_search_discovery(deps, "not valid json at all")

    assert len(deps.agent_state.discovered_searches) == 0


def test_slim_graph_result_replaces_verbose_json() -> None:
    graph = StrategyGraph(graph_id="g1", name="Test", site_id="plasmodb")
    graph.record_type = "transcript"

    step = PlanStepNode(
        search_name="GenesByTaxon",
        display_name="Genes by Taxon",
        parameters={"organism": "Plasmodium falciparum 3D7"},
    )
    graph.add_step(step)
    sync_state = WDKSyncState()
    sync_state.step_counts[step.id] = 1234

    # Build a StepOkResponse-like JSON string
    result_json = json.dumps({
        "ok": True,
        "step": {
            "id": step.id,
            "kind": "search",
            "displayName": "Genes by Taxon",
            "searchName": "GenesByTaxon",
            "recordType": "transcript",
            "parameters": {"organism": "Plasmodium falciparum 3D7"},
            "estimatedSize": 1234,
            "isBuilt": False,
            "isFiltered": False,
        },
        "graphId": "g1",
        "graphSnapshot": {"graphId": "g1", "steps": [], "edges": []},
    })

    slim = _slim_graph_result(result_json, graph, sync_state)

    assert slim is not None
    assert step.id in slim
    assert "ok:" in slim
    # The slim result should be much shorter than the full JSON
    assert len(slim) < len(result_json)


def test_slim_graph_result_returns_none_for_invalid_json() -> None:
    graph = StrategyGraph(graph_id="g1", name="Test", site_id="plasmodb")

    result = _slim_graph_result("not json", graph, None)

    assert result is None


def test_slim_graph_result_returns_none_for_error_response() -> None:
    graph = StrategyGraph(graph_id="g1", name="Test", site_id="plasmodb")

    result_json = json.dumps({
        "ok": False,
        "code": "VALIDATION_ERROR",
        "message": "Bad params",
    })

    result = _slim_graph_result(result_json, graph, None)

    assert result is None
