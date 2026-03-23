"""Unit tests for services.strategies.engine.graph_ops.GraphOpsMixin."""

from veupath_chatbot.domain.strategy.ast import PlanStepNode
from veupath_chatbot.domain.strategy.ops import CombineOp
from veupath_chatbot.domain.strategy.session import StrategyGraph, StrategySession
from veupath_chatbot.services.strategies.engine.helpers import StrategyToolsHelpers
from veupath_chatbot.tests.fixtures.builders import (
    make_combine,
    make_leaf,
    make_transform,
)


def _make_session_with_graph(
    graph_id: str = "g1",
    record_type: str | None = "gene",
) -> tuple[StrategySession, StrategyGraph]:
    session = StrategySession("plasmodb")
    graph = session.create_graph("Test", graph_id=graph_id)
    if record_type:
        graph.record_type = record_type
    return session, graph


def _make_mixin(
    session: StrategySession | None = None,
) -> StrategyToolsHelpers:
    if session is None:
        session, _ = _make_session_with_graph()
    return StrategyToolsHelpers(session)


def _leaf(
    step_id: str, name: str = "GenesByTextSearch", display: str | None = None
) -> PlanStepNode:
    return make_leaf(
        step_id, name=name, display=display, parameters={"text_expression": "test"}
    )


# ── _derive_strategy_name ─────────────────────────────────────────────


class TestDeriveStrategyName:
    def test_search_step_uses_display_name(self) -> None:
        mixin = _make_mixin()
        step = _leaf("s1", display="Kinase Search")
        name = mixin._derive_strategy_name("gene", step)
        assert "Kinase Search" in name

    def test_search_step_uses_search_name_fallback(self) -> None:
        mixin = _make_mixin()
        step = _leaf("s1", name="GenesByTextSearch")
        name = mixin._derive_strategy_name("gene", step)
        assert "GenesByTextSearch" in name

    def test_combine_step_with_operator(self) -> None:
        mixin = _make_mixin()
        left = _leaf("s1")
        right = _leaf("s2")
        step = make_combine("c1", left, right, CombineOp.INTERSECT)
        name = mixin._derive_strategy_name("gene", step)
        assert name  # Should produce a non-empty name

    def test_combine_step_with_display_name(self) -> None:
        mixin = _make_mixin()
        left = _leaf("s1")
        right = _leaf("s2")
        step = make_combine("c1", left, right)
        step.display_name = "My Custom Combine"
        name = mixin._derive_strategy_name("gene", step)
        assert "My Custom Combine" in name

    def test_no_record_type_fallback(self) -> None:
        mixin = _make_mixin()
        step = PlanStepNode(search_name="S1", parameters={}, id="s1")
        name = mixin._derive_strategy_name(None, step)
        assert name  # Should not crash

    def test_empty_display_name_falls_back(self) -> None:
        mixin = _make_mixin()
        step = PlanStepNode(
            search_name="",
            parameters={},
            display_name="  ",
            id="s1",
        )
        name = mixin._derive_strategy_name("gene", step)
        assert "Gene" in name or "strategy" in name.lower()

    def test_record_type_prepended_when_missing(self) -> None:
        mixin = _make_mixin()
        step = _leaf("s1", name="TextSearch", display="TextSearch")
        name = mixin._derive_strategy_name("gene", step)
        # "gene" not in "TextSearch", so record type should be prepended
        assert "Gene" in name

    def test_record_type_not_duplicated(self) -> None:
        mixin = _make_mixin()
        step = _leaf("s1", display="Gene Expression Search")
        name = mixin._derive_strategy_name("gene", step)
        # "gene" is already in the display name, so should not be prepended again
        assert name.count("Gene") == 1

    def test_name_truncated_to_120_chars(self) -> None:
        mixin = _make_mixin()
        step = _leaf("s1", display="A" * 200)
        name = mixin._derive_strategy_name("gene", step)
        assert len(name) <= 120


# ── _derive_strategy_description ──────────────────────────────────────


class TestDeriveStrategyDescription:
    def test_search_step_description(self) -> None:
        mixin = _make_mixin()
        step = _leaf("s1", display="Kinase Search")
        desc = mixin._derive_strategy_description("gene", step)
        assert "Find" in desc
        assert "gene" in desc
        assert "Kinase Search" in desc

    def test_transform_step_description(self) -> None:
        mixin = _make_mixin()
        leaf = _leaf("s1")
        step = make_transform("t1", leaf)
        desc = mixin._derive_strategy_description("gene", step)
        assert "Transform" in desc

    def test_combine_step_description(self) -> None:
        mixin = _make_mixin()
        left = _leaf("s1")
        right = _leaf("s2")
        step = make_combine("c1", left, right, CombineOp.UNION)
        desc = mixin._derive_strategy_description("gene", step)
        assert "Combine" in desc

    def test_no_record_type_description(self) -> None:
        mixin = _make_mixin()
        step = _leaf("s1", display="Text Search")
        desc = mixin._derive_strategy_description(None, step)
        assert "Find" in desc
        assert "Text Search" in desc

    def test_empty_display_name_falls_back(self) -> None:
        mixin = _make_mixin()
        step = PlanStepNode(search_name="", parameters={}, display_name="", id="s1")
        desc = mixin._derive_strategy_description("gene", step)
        assert "results" in desc


# ── _serialize_step ───────────────────────────────────────────────────


class TestSerializeStep:
    def test_search_step_serialization(self) -> None:
        session, graph = _make_session_with_graph()
        mixin = StrategyToolsHelpers(session)
        step = _leaf("s1", display="My Search")
        graph.add_step(step)
        result = mixin._serialize_step(graph, step)
        assert result["id"] == "s1"
        assert result["kind"] == "search"
        assert result["displayName"] == "My Search"
        assert result["searchName"] == "GenesByTextSearch"
        assert result["isBuilt"] is False

    def test_combine_step_serialization(self) -> None:
        session, graph = _make_session_with_graph()
        mixin = StrategyToolsHelpers(session)
        left = _leaf("s1")
        right = _leaf("s2")
        step = make_combine("c1", left, right, CombineOp.UNION)
        graph.add_step(left)
        graph.add_step(right)
        graph.add_step(step)
        result = mixin._serialize_step(graph, step)
        assert result["kind"] == "combine"
        assert result["operator"] == "UNION"
        assert result["primaryInputStepId"] == "s1"
        assert result["secondaryInputStepId"] == "s2"
        assert result["searchName"] is not None  # WDK always includes searchName

    def test_transform_step_serialization(self) -> None:
        session, graph = _make_session_with_graph()
        mixin = StrategyToolsHelpers(session)
        leaf = _leaf("s1")
        step = make_transform("t1", leaf)
        graph.add_step(leaf)
        graph.add_step(step)
        result = mixin._serialize_step(graph, step)
        assert result["kind"] == "transform"
        assert result["primaryInputStepId"] == "s1"
        assert result["searchName"] == "GenesByOrthologs"

    def test_wdk_step_id_included_when_available(self) -> None:
        session, graph = _make_session_with_graph()
        mixin = StrategyToolsHelpers(session)
        step = _leaf("s1")
        graph.add_step(step)
        graph.wdk_step_ids["s1"] = 42
        result = mixin._serialize_step(graph, step)
        assert result["wdkStepId"] == 42
        assert result["isBuilt"] is True

    def test_estimated_size_included_when_available(self) -> None:
        session, graph = _make_session_with_graph()
        mixin = StrategyToolsHelpers(session)
        step = _leaf("s1")
        graph.add_step(step)
        graph.step_counts["s1"] = 1234
        result = mixin._serialize_step(graph, step)
        assert result["estimatedSize"] == 1234

    def test_parameters_omitted_when_empty(self) -> None:
        session, graph = _make_session_with_graph()
        mixin = StrategyToolsHelpers(session)
        step = PlanStepNode(search_name="S1", parameters={}, id="s1")
        graph.add_step(step)
        result = mixin._serialize_step(graph, step)
        assert "parameters" not in result

    def test_parameters_included_when_present(self) -> None:
        session, graph = _make_session_with_graph()
        mixin = StrategyToolsHelpers(session)
        step = _leaf("s1")
        graph.add_step(step)
        result = mixin._serialize_step(graph, step)
        assert "parameters" in result
        assert result["parameters"]["text_expression"] == "test"


# ── _build_graph_snapshot ─────────────────────────────────────────────


class TestBuildGraphSnapshot:
    def test_snapshot_structure(self) -> None:
        session, graph = _make_session_with_graph()
        mixin = StrategyToolsHelpers(session)
        s1 = _leaf("s1")
        s2 = _leaf("s2")
        c1 = make_combine("c1", s1, s2)
        graph.add_step(s1)
        graph.add_step(s2)
        graph.add_step(c1)
        graph.last_step_id = "c1"
        graph.record_type = "gene"
        graph.name = "My Strategy"
        snapshot = mixin._build_graph_snapshot(graph)
        assert snapshot["graphId"] == "g1"
        assert snapshot["rootStepId"] == "c1"
        assert len(snapshot["steps"]) == 3
        assert len(snapshot["edges"]) > 0  # edges from inputs

    def test_snapshot_multiple_roots_no_root_step_id(self) -> None:
        """When graph has multiple roots, rootStepId should be None."""
        session, graph = _make_session_with_graph()
        mixin = StrategyToolsHelpers(session)
        s1 = _leaf("s1")
        s2 = _leaf("s2")
        graph.add_step(s1)
        graph.add_step(s2)
        graph.record_type = "gene"
        snapshot = mixin._build_graph_snapshot(graph)
        assert "rootStepId" not in snapshot

    def test_snapshot_edges_primary_and_secondary(self) -> None:
        session, graph = _make_session_with_graph()
        mixin = StrategyToolsHelpers(session)
        s1 = _leaf("s1")
        s2 = _leaf("s2")
        c1 = make_combine("c1", s1, s2)
        graph.add_step(s1)
        graph.add_step(s2)
        graph.add_step(c1)
        graph.record_type = "gene"
        snapshot = mixin._build_graph_snapshot(graph)
        edges = snapshot["edges"]
        primary_edges = [e for e in edges if e["kind"] == "primary"]
        secondary_edges = [e for e in edges if e["kind"] == "secondary"]
        assert len(primary_edges) >= 1
        assert len(secondary_edges) >= 1

    def test_empty_graph_snapshot(self) -> None:
        session, graph = _make_session_with_graph()
        mixin = StrategyToolsHelpers(session)
        snapshot = mixin._build_graph_snapshot(graph)
        assert snapshot["steps"] == []
        assert snapshot["edges"] == []
        assert "rootStepId" not in snapshot


# ── _build_context_plan ───────────────────────────────────────────────


class TestBuildContextPlan:
    def test_with_single_root(self) -> None:
        session, graph = _make_session_with_graph()
        mixin = StrategyToolsHelpers(session)
        step = _leaf("s1", display="Text Search")
        graph.add_step(step)
        graph.record_type = "gene"
        result = mixin._build_context_plan(graph)
        assert result is not None
        assert result.record_type == "gene"
        assert result.plan is not None
        assert result.graph_id is not None

    def test_returns_none_without_record_type(self) -> None:
        session, graph = _make_session_with_graph(record_type=None)
        mixin = StrategyToolsHelpers(session)
        step = _leaf("s1")
        graph.add_step(step)
        result = mixin._build_context_plan(graph)
        assert result is None

    def test_returns_none_when_no_roots(self) -> None:
        session, graph = _make_session_with_graph()
        mixin = StrategyToolsHelpers(session)
        result = mixin._build_context_plan(graph)
        assert result is None

    def test_derives_name_for_placeholder(self) -> None:
        session, graph = _make_session_with_graph()
        mixin = StrategyToolsHelpers(session)
        step = _leaf("s1", display="Text Search")
        graph.add_step(step)
        graph.record_type = "gene"
        graph.name = "Draft Graph"
        result = mixin._build_context_plan(graph)
        assert result is not None
        # Name should be derived, not "Draft Graph"
        assert result.name != "Draft Graph"

    def test_keeps_existing_name(self) -> None:
        session, graph = _make_session_with_graph()
        mixin = StrategyToolsHelpers(session)
        step = _leaf("s1")
        graph.add_step(step)
        graph.record_type = "gene"
        graph.name = "My Custom Name"
        result = mixin._build_context_plan(graph)
        assert result is not None
        assert result.name == "My Custom Name"

    def test_falls_back_to_last_step_id(self) -> None:
        """When multiple roots exist, falls back to last_step_id."""
        session, graph = _make_session_with_graph()
        mixin = StrategyToolsHelpers(session)
        s1 = _leaf("s1")
        s2 = _leaf("s2")
        graph.add_step(s1)
        graph.add_step(s2)
        graph.record_type = "gene"
        graph.last_step_id = "s2"
        result = mixin._build_context_plan(graph)
        assert result is not None
        # Should use s2 as root since it's last_step_id
        assert result.plan["root"]["id"] == "s2"


# ── _with_plan_payload ────────────────────────────────────────────────


class TestWithPlanPayload:
    def test_enriches_payload_with_plan(self) -> None:
        session, graph = _make_session_with_graph()
        mixin = StrategyToolsHelpers(session)
        step = _leaf("s1")
        graph.add_step(step)
        graph.record_type = "gene"
        payload = {"ok": True}
        result = mixin._with_plan_payload(graph, payload)
        assert result["ok"] is True
        assert "graphId" in result
        assert "recordType" in result

    def test_sets_defaults_when_no_plan(self) -> None:
        session, graph = _make_session_with_graph(record_type=None)
        mixin = StrategyToolsHelpers(session)
        payload = {"ok": True}
        result = mixin._with_plan_payload(graph, payload)
        assert result["graphId"] == "g1"
        assert result["graphName"] == "Test"


# ── _with_full_graph ──────────────────────────────────────────────────


class TestWithFullGraph:
    def test_includes_graph_snapshot(self) -> None:
        session, graph = _make_session_with_graph()
        mixin = StrategyToolsHelpers(session)
        step = _leaf("s1")
        graph.add_step(step)
        graph.record_type = "gene"
        payload = {"ok": True}
        result = mixin._with_full_graph(graph, payload)
        assert "graphSnapshot" in result
        assert result["graphSnapshot"]["graphId"] == "g1"
