"""Comprehensive tests for pydantic-ai lifecycle hooks.

Covers _track_search_discovery, _slim_graph_result, and _merge_auto_build
from pathfinder.ai.agents._hooks.
"""

import json

from pathfinder.ai.agents._hooks import (
    _merge_auto_build,
    _RawSearchOverview,
    _slim_graph_result,
    _track_search_discovery,
)
from pathfinder.ai.agents.state import AgentToolState
from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.domain.strategy.ast import COMBINE_SEARCH_NAME, StrategyStepNode
from pathfinder.domain.strategy.ops import CombineOp
from pathfinder.domain.strategy.session import StrategyGraph, StrategySession
from pathfinder.services.strategies.sync_state import WDKSyncState

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_deps(site_id: str = "plasmodb.org") -> AgentDeps:
    return AgentDeps(
        site_id=site_id,
        strategy_session=StrategySession(site_id=site_id),
        agent_state=AgentToolState(),
    )


def _make_step_ok_json(step_id: str, **overrides: object) -> str:
    """Build a StepOkResponse-shaped JSON string for _slim_graph_result tests.

    Accepts keyword overrides merged into a default step dict.  Recognised
    keys: searchName, displayName, recordType, parameters, operator,
    primaryInputStepId, secondaryInputStepId, ok.
    """
    ok = overrides.pop("ok", True)
    step: dict[str, object] = {
        "id": step_id,
        "kind": "search",
        "displayName": overrides.pop("displayName", "Genes by Taxon"),
        "searchName": overrides.pop("searchName", "GenesByTaxon"),
        "recordType": overrides.pop("recordType", "transcript"),
        "parameters": overrides.pop("parameters", {}),
        "isBuilt": False,
        "isFiltered": False,
    }
    for key in ("operator", "primaryInputStepId", "secondaryInputStepId"):
        val = overrides.pop(key, None)
        if val is not None:
            step[key] = val
    step.update(overrides)
    return json.dumps({"ok": ok, "step": step})


# ===========================================================================
# _track_search_discovery
# ===========================================================================


class TestTrackSearchDiscovery:
    """Tests for _track_search_discovery."""

    def test_discovery_registers_search_with_correct_fields(self) -> None:
        """Verify all SearchOverview fields are populated correctly."""
        deps = _make_deps()
        result_text = json.dumps({
            "searchName": "GenesByGoTerm",
            "displayName": "Genes by GO Term",
            "recordType": "transcript",
            "description": "Find genes annotated with a GO term",
            "required": [
                {"name": "organism", "type": "string"},
                {"name": "GoTerm", "type": "string"},
            ],
            "optional": [
                {"name": "o-fields", "type": "string"},
                {"name": "evidence_code", "type": "string"},
            ],
        })

        _track_search_discovery(deps, result_text)

        assert deps.agent_state.is_search_discovered("GenesByGoTerm")
        overview = deps.agent_state.get_overview("GenesByGoTerm")
        assert overview is not None
        assert overview.search_name == "GenesByGoTerm"
        assert overview.display_name == "Genes by GO Term"
        assert overview.record_type == "transcript"
        assert overview.description == "Find genes annotated with a GO term"
        assert overview.required_params == ["organism", "GoTerm"]
        assert overview.parameter_names == [
            "organism", "GoTerm", "o-fields", "evidence_code",
        ]

    def test_discovery_handles_camel_case_json(self) -> None:
        """The tool result uses camelCase — verify _RawSearchOverview parses it."""
        raw_json = {
            "searchName": "GenesByLocation",
            "displayName": "Genes by Genomic Location",
            "recordType": "gene",
            "description": "Chromosomal region search",
            "required": [{"name": "sequenceId", "type": "string"}],
            "optional": [],
        }

        parsed = _RawSearchOverview.model_validate(raw_json)

        assert parsed.searchName == "GenesByLocation"
        assert parsed.displayName == "Genes by Genomic Location"
        assert parsed.recordType == "gene"
        assert parsed.description == "Chromosomal region search"
        assert len(parsed.required) == 1
        assert parsed.required[0].name == "sequenceId"
        assert parsed.optional == []

    def test_discovery_handles_missing_optional_fields(self) -> None:
        """Result JSON missing displayName, description, optional — should still register."""
        deps = _make_deps()
        result_text = json.dumps({
            "searchName": "GenesByTaxon",
            "recordType": "transcript",
            "required": [{"name": "organism", "type": "string"}],
        })

        _track_search_discovery(deps, result_text)

        assert deps.agent_state.is_search_discovered("GenesByTaxon")
        overview = deps.agent_state.get_overview("GenesByTaxon")
        assert overview is not None
        # displayName falls back to searchName when empty
        assert overview.display_name == "GenesByTaxon"
        assert overview.description == ""
        assert overview.required_params == ["organism"]
        assert overview.parameter_names == ["organism"]

    def test_discovery_ignores_malformed_json(self) -> None:
        """Completely invalid JSON should not crash or register anything."""
        deps = _make_deps()

        _track_search_discovery(deps, "this is not json {{{")

        assert len(deps.agent_state.discovered_searches) == 0

    def test_discovery_ignores_empty_search_name(self) -> None:
        """Empty searchName should not register."""
        deps = _make_deps()
        result_text = json.dumps({
            "searchName": "",
            "displayName": "Empty",
        })

        _track_search_discovery(deps, result_text)

        assert len(deps.agent_state.discovered_searches) == 0

    def test_discovery_ignores_non_dict_json(self) -> None:
        """A JSON array should not register anything."""
        deps = _make_deps()

        _track_search_discovery(deps, json.dumps([1, 2, 3]))

        assert len(deps.agent_state.discovered_searches) == 0

    def test_discovery_extra_fields_ignored(self) -> None:
        """Extra keys in the JSON should be silently ignored (extra='ignore')."""
        deps = _make_deps()
        result_text = json.dumps({
            "searchName": "GenesByTaxon",
            "displayName": "Genes by Taxon",
            "recordType": "transcript",
            "description": "desc",
            "required": [],
            "optional": [],
            "someExtraField": "should be ignored",
            "anotherExtra": 42,
        })

        _track_search_discovery(deps, result_text)

        assert deps.agent_state.is_search_discovered("GenesByTaxon")

    def test_discovery_record_type_defaults_to_transcript(self) -> None:
        """When recordType is missing, overview defaults to 'transcript'."""
        deps = _make_deps()
        result_text = json.dumps({
            "searchName": "GenesByTextSearch",
            "required": [],
        })

        _track_search_discovery(deps, result_text)

        overview = deps.agent_state.get_overview("GenesByTextSearch")
        assert overview is not None
        assert overview.record_type == "transcript"

    def test_discovery_multiple_searches_registered(self) -> None:
        """Registering two searches keeps both in state."""
        deps = _make_deps()

        _track_search_discovery(deps, json.dumps({
            "searchName": "GenesByTaxon",
            "required": [{"name": "organism"}],
        }))
        _track_search_discovery(deps, json.dumps({
            "searchName": "GenesByGoTerm",
            "required": [{"name": "GoTerm"}],
        }))

        assert deps.agent_state.is_search_discovered("GenesByTaxon")
        assert deps.agent_state.is_search_discovered("GenesByGoTerm")
        assert len(deps.agent_state.discovered_searches) == 2


# ===========================================================================
# _slim_graph_result
# ===========================================================================


class TestSlimGraphResult:
    """Tests for _slim_graph_result."""

    def test_slim_leaf_step(self) -> None:
        """Leaf step with search_name and display_name produces a slim one-liner."""
        graph = StrategyGraph(graph_id="g1", name="Test", site_id="plasmodb")
        step = StrategyStepNode(
            search_name="GenesByTaxon",
            display_name="P. falciparum genes",
            parameters={"organism": "Plasmodium falciparum 3D7"},
        )
        graph.add_step(step)
        sync_state = WDKSyncState()
        sync_state.step_counts[step.id] = 5678

        result_json = _make_step_ok_json(
            step.id,
            searchName="GenesByTaxon",
            displayName="P. falciparum genes",
        )

        slim = _slim_graph_result(result_json, graph, sync_state)

        assert slim is not None
        assert "ok:" in slim
        assert step.id in slim
        assert "GenesByTaxon" in slim
        assert '"P. falciparum genes"' in slim
        assert "5,678 genes" in slim

    def test_slim_combine_step(self) -> None:
        """Combine step with operator and two inputs."""
        graph = StrategyGraph(graph_id="g1", name="Test", site_id="plasmodb")

        step_a = StrategyStepNode(search_name="GenesByTaxon", display_name="A")
        graph.add_step(step_a)

        step_b = StrategyStepNode(search_name="GenesByGoTerm", display_name="B")
        graph.add_step(step_b)

        combine_step = StrategyStepNode(
            search_name=COMBINE_SEARCH_NAME,
            display_name="A intersect B",
            primary_input=step_a,
            secondary_input=step_b,
            operator=CombineOp.INTERSECT,
        )
        graph.add_step(combine_step)
        sync_state = WDKSyncState()
        sync_state.step_counts[combine_step.id] = 42

        result_json = _make_step_ok_json(
            combine_step.id,
            searchName=COMBINE_SEARCH_NAME,
            displayName="A intersect B",
            operator="INTERSECT",
            primaryInputStepId=step_a.id,
            secondaryInputStepId=step_b.id,
        )

        slim = _slim_graph_result(result_json, graph, sync_state)

        assert slim is not None
        assert "ok:" in slim
        assert combine_step.id in slim
        # Combine steps show the operator with both input IDs
        assert f"INTERSECT({step_a.id}, {step_b.id})" in slim
        assert "42 genes" in slim

    def test_slim_transform_step(self) -> None:
        """Transform step with only primary input."""
        graph = StrategyGraph(graph_id="g1", name="Test", site_id="plasmodb")

        base_step = StrategyStepNode(search_name="GenesByTaxon", display_name="Base")
        graph.add_step(base_step)

        transform = StrategyStepNode(
            search_name="GenesByOrthologPattern",
            display_name="Orthologs",
            primary_input=base_step,
        )
        graph.add_step(transform)
        sync_state = WDKSyncState()
        sync_state.step_counts[transform.id] = 100

        result_json = _make_step_ok_json(
            transform.id,
            searchName="GenesByOrthologPattern",
            displayName="Orthologs",
            primaryInputStepId=base_step.id,
        )

        slim = _slim_graph_result(result_json, graph, sync_state)

        assert slim is not None
        assert "ok:" in slim
        assert transform.id in slim
        assert "GenesByOrthologPattern" in slim
        assert '"Orthologs"' in slim
        assert "100 genes" in slim

    def test_slim_returns_none_for_error(self) -> None:
        """Tool error response (ok=false) returns None."""
        graph = StrategyGraph(graph_id="g1", name="Test", site_id="plasmodb")

        error_json = json.dumps({
            "ok": False,
            "code": "VALIDATION_ERROR",
            "message": "Parameter 'organism' is required",
        })

        result = _slim_graph_result(error_json, graph, None)
        assert result is None

    def test_slim_returns_none_for_non_json(self) -> None:
        """Plain text (not JSON) returns None."""
        graph = StrategyGraph(graph_id="g1", name="Test", site_id="plasmodb")

        result = _slim_graph_result("This is plain text, not JSON", graph, None)
        assert result is None

    def test_slim_returns_none_for_missing_step_field(self) -> None:
        """JSON without required 'step' field fails validation and returns None."""
        graph = StrategyGraph(graph_id="g1", name="Test", site_id="plasmodb")

        result = _slim_graph_result(json.dumps({"ok": True}), graph, None)
        assert result is None

    def test_slim_step_without_count_omits_gene_count(self) -> None:
        """When sync_state has no entry for the step, the slim omits gene count."""
        graph = StrategyGraph(graph_id="g1", name="Test", site_id="plasmodb")
        step = StrategyStepNode(
            search_name="GenesByTaxon",
            display_name="Test Step",
        )
        graph.add_step(step)
        # Deliberately do NOT set sync_state.step_counts[step.id]

        result_json = _make_step_ok_json(
            step.id,
            searchName="GenesByTaxon",
            displayName="Test Step",
        )

        slim = _slim_graph_result(result_json, graph, None)

        assert slim is not None
        assert "genes" not in slim
        assert step.id in slim


# ===========================================================================
# _merge_auto_build
# ===========================================================================


class TestMergeAutoBuild:
    """Tests for _merge_auto_build."""

    def test_merge_with_valid_json(self) -> None:
        """Original JSON dict + extra dict are merged correctly."""
        original = json.dumps({"ok": True, "step": {"id": "step_1"}})
        extra = {"autoBuild": {"wdkStrategyId": 123, "rootCount": 500}}

        result = _merge_auto_build(original, extra)

        parsed = json.loads(result)
        # Original fields preserved
        assert parsed["ok"] is True
        assert parsed["step"]["id"] == "step_1"
        # Extra fields merged
        assert parsed["autoBuild"]["wdkStrategyId"] == 123
        assert parsed["autoBuild"]["rootCount"] == 500

    def test_merge_with_invalid_json(self) -> None:
        """Non-JSON original + extra produces just the extra."""
        extra = {"autoBuild": {"ok": False, "error": "push failed"}}

        result = _merge_auto_build("not valid json", extra)

        parsed = json.loads(result)
        assert parsed["autoBuild"]["ok"] is False
        assert parsed["autoBuild"]["error"] == "push failed"
        # No stale keys from original
        assert "ok" not in parsed or parsed.get("ok") is not True

    def test_merge_with_empty_original(self) -> None:
        """Empty string original + extra produces just the extra."""
        extra = {"autoBuild": {"wdkStrategyId": 456}}

        result = _merge_auto_build("", extra)

        parsed = json.loads(result)
        assert parsed["autoBuild"]["wdkStrategyId"] == 456

    def test_merge_with_none_like_empty(self) -> None:
        """Empty original starts from empty dict, extra is merged."""
        extra = {"key": "value"}

        result = _merge_auto_build("", extra)

        parsed = json.loads(result)
        assert parsed == {"key": "value"}

    def test_merge_extra_overwrites_conflicting_keys(self) -> None:
        """When extra has a key that's also in original, extra wins."""
        original = json.dumps({"status": "pending"})
        extra = {"status": "complete", "detail": "done"}

        result = _merge_auto_build(original, extra)

        parsed = json.loads(result)
        assert parsed["status"] == "complete"
        assert parsed["detail"] == "done"

    def test_merge_produces_valid_json(self) -> None:
        """Result is always valid JSON regardless of original format."""
        original = json.dumps({"a": 1})
        extra = {"b": 2}

        result = _merge_auto_build(original, extra)

        # Should not raise
        parsed = json.loads(result)
        assert parsed["a"] == 1
        assert parsed["b"] == 2
