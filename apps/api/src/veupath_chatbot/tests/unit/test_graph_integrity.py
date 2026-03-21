"""Unit tests for services.strategies.engine.graph_integrity."""

import pytest
from pydantic import ValidationError

from veupath_chatbot.domain.strategy.ast import PlanStepNode
from veupath_chatbot.domain.strategy.session import StrategyGraph
from veupath_chatbot.services.strategies.engine.graph_integrity import (
    GraphIntegrityError,
    find_root_step_ids,
    validate_graph_integrity,
)
from veupath_chatbot.tests.fixtures.builders import make_combine, make_leaf


def _graph_with_steps(*steps: PlanStepNode) -> StrategyGraph:
    graph = StrategyGraph("g1", "Test", "plasmodb")
    for step in steps:
        graph.add_step(step)
    return graph


# ── GraphIntegrityError ──────────────────────────────────────────────


class TestGraphIntegrityError:
    def test_to_dict_minimal(self) -> None:
        err = GraphIntegrityError(code="TEST_CODE", message="Something broke")
        d = err.to_dict()
        assert d["code"] == "TEST_CODE"
        assert d["message"] == "Something broke"
        assert "stepId" not in d
        assert "inputStepId" not in d
        assert "kind" not in d

    def test_to_dict_with_all_fields(self) -> None:
        err = GraphIntegrityError(
            code="REF",
            message="bad ref",
            step_id="s1",
            input_step_id="s2",
            kind="primary_input",
        )
        d = err.to_dict()
        assert d["stepId"] == "s1"
        assert d["inputStepId"] == "s2"
        assert d["kind"] == "primary_input"

    def test_frozen(self) -> None:
        err = GraphIntegrityError(code="A", message="B")
        with pytest.raises(ValidationError):
            err.code = "C"  # type: ignore[misc]


# ── find_root_step_ids ────────────────────────────────────────────────


class TestFindRootStepIds:
    def test_empty_graph(self) -> None:
        graph = StrategyGraph("g1", "Test", "plasmodb")
        assert find_root_step_ids(graph) == []

    def test_single_root(self) -> None:
        s1 = make_leaf("s1")
        graph = _graph_with_steps(s1)
        assert find_root_step_ids(graph) == ["s1"]

    def test_multiple_roots_sorted(self) -> None:
        graph = _graph_with_steps(make_leaf("z"), make_leaf("a"), make_leaf("m"))
        assert find_root_step_ids(graph) == ["a", "m", "z"]

    def test_combine_leaves_single_root(self) -> None:
        s1 = make_leaf("s1")
        s2 = make_leaf("s2")
        c1 = make_combine("c1", s1, s2)
        graph = _graph_with_steps(s1, s2, c1)
        assert find_root_step_ids(graph) == ["c1"]


# ── validate_graph_integrity ──────────────────────────────────────────


class TestValidateGraphIntegrity:
    def test_empty_graph(self) -> None:
        graph = StrategyGraph("g1", "Test", "plasmodb")
        errors = validate_graph_integrity(graph)
        assert len(errors) == 1
        assert errors[0].code == "EMPTY_GRAPH"

    def test_valid_single_step(self) -> None:
        graph = _graph_with_steps(make_leaf("s1"))
        errors = validate_graph_integrity(graph)
        assert errors == []

    def test_validmake_combine(self) -> None:
        s1 = make_leaf("s1")
        s2 = make_leaf("s2")
        c1 = make_combine("c1", s1, s2)
        graph = _graph_with_steps(s1, s2, c1)
        errors = validate_graph_integrity(graph)
        assert errors == []

    def test_multiple_roots_error(self) -> None:
        graph = _graph_with_steps(make_leaf("s1"), make_leaf("s2"))
        errors = validate_graph_integrity(graph)
        codes = [e.code for e in errors]
        assert "MULTIPLE_ROOTS" in codes

    def test_dangling_primary_input_reference(self) -> None:
        """Step references a primary input that doesn't exist in graph."""
        phantom = make_leaf("phantom")
        step = PlanStepNode(
            search_name="Transform",
            parameters={},
            primary_input=phantom,
            id="t1",
        )
        graph = StrategyGraph("g1", "Test", "plasmodb")
        # Manually add just the step, not its input
        graph.steps["t1"] = step
        graph.roots = {"t1"}
        errors = validate_graph_integrity(graph)
        codes = [e.code for e in errors]
        assert "UNKNOWN_STEP_REFERENCE" in codes
        ref_error = next(e for e in errors if e.code == "UNKNOWN_STEP_REFERENCE")
        assert ref_error.step_id == "t1"
        assert ref_error.input_step_id == "phantom"
        assert ref_error.kind == "primary_input"

    def test_dangling_secondary_input_reference(self) -> None:
        """Step references a secondary input that doesn't exist in graph."""
        left = make_leaf("s1")
        phantom = make_leaf("phantom")
        combine = make_combine("c1", left, phantom)
        graph = StrategyGraph("g1", "Test", "plasmodb")
        graph.steps["s1"] = left
        graph.steps["c1"] = combine
        graph.roots = {"c1"}
        errors = validate_graph_integrity(graph)
        codes = [e.code for e in errors]
        assert "UNKNOWN_STEP_REFERENCE" in codes
        ref_errors = [e for e in errors if e.code == "UNKNOWN_STEP_REFERENCE"]
        kinds = {e.kind for e in ref_errors}
        assert "secondary_input" in kinds

    def test_no_roots_error(self) -> None:
        """Graph with steps but no roots should produce NO_ROOTS error."""
        graph = StrategyGraph("g1", "Test", "plasmodb")
        step = make_leaf("s1")
        graph.steps["s1"] = step
        graph.roots = set()  # Manually clear roots
        errors = validate_graph_integrity(graph)
        codes = [e.code for e in errors]
        assert "NO_ROOTS" in codes

    def test_multiple_errors_combined(self) -> None:
        """Graph can have multiple simultaneous errors."""
        # Two disconnected steps each with dangling references
        phantom_a = make_leaf("pa")
        phantom_b = make_leaf("pb")
        step_a = PlanStepNode(
            search_name="T", parameters={}, primary_input=phantom_a, id="a"
        )
        step_b = PlanStepNode(
            search_name="T", parameters={}, primary_input=phantom_b, id="b"
        )
        graph = StrategyGraph("g1", "Test", "plasmodb")
        graph.steps = {"a": step_a, "b": step_b}
        graph.roots = {"a", "b"}
        errors = validate_graph_integrity(graph)
        # Should have MULTIPLE_ROOTS + 2x UNKNOWN_STEP_REFERENCE
        codes = [e.code for e in errors]
        assert codes.count("UNKNOWN_STEP_REFERENCE") == 2
        assert "MULTIPLE_ROOTS" in codes
