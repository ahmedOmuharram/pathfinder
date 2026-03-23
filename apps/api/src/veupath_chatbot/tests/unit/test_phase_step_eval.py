"""Tests for phase_step_eval.py and _evaluation.py helpers.

Tests focus on pure functions:
- _extract_eval_counts from various result shapes
- _f1_from_counts F1 computation via canonical metrics engine
- _collect_combine_nodes for tree structure analysis
- _build_subtree_with_operator for operator swaps
"""

import pytest

from veupath_chatbot.services.experiment.step_analysis._evaluation import (
    _EvalCounts,
    _extract_eval_counts,
    _f1_from_counts,
)
from veupath_chatbot.services.experiment.step_analysis._tree_utils import (
    _build_subtree_with_operator,
    _collect_combine_nodes,
    _node_id,
)
from veupath_chatbot.services.experiment.types.control_result import (
    ControlSetData,
    ControlTargetData,
    ControlTestResult,
)


class TestExtractEvalCounts:
    """_extract_eval_counts pulls structured counts from control-test results."""

    def test_complete_result(self) -> None:
        result = ControlTestResult(
            positive=ControlSetData(
                controls_count=10,
                intersection_count=8,
                intersection_ids=["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8"],
            ),
            negative=ControlSetData(
                controls_count=20,
                intersection_count=3,
                intersection_ids=["N1", "N2", "N3"],
            ),
            target=ControlTargetData(result_count=100),
        )
        counts = _extract_eval_counts(result)
        assert counts.pos_hits == 8
        assert counts.pos_total == 10
        assert counts.neg_hits == 3
        assert counts.neg_total == 20
        assert counts.total_results == 100
        assert len(counts.pos_ids) == 8
        assert len(counts.neg_ids) == 3

    def test_empty_result(self) -> None:
        counts = _extract_eval_counts(ControlTestResult())
        assert counts.pos_hits == 0
        assert counts.pos_total == 0
        assert counts.neg_hits == 0
        assert counts.neg_total == 0
        assert counts.total_results == 0
        assert counts.pos_ids == []
        assert counts.neg_ids == []

    def test_none_sections(self) -> None:
        result = ControlTestResult(positive=None, negative=None)
        counts = _extract_eval_counts(result)
        assert counts.pos_hits == 0
        assert counts.total_results == 0

    def test_missing_intersection_ids(self) -> None:
        """When intersectionIds is empty, pos_ids is empty."""
        result = ControlTestResult(
            positive=ControlSetData(controls_count=5, intersection_count=3),
            negative=ControlSetData(controls_count=10, intersection_count=1),
            target=ControlTargetData(result_count=50),
        )
        counts = _extract_eval_counts(result)
        assert counts.pos_hits == 3
        assert counts.pos_ids == []
        assert counts.neg_ids == []


class TestF1FromCounts:
    """_f1_from_counts computes F1 via the canonical metrics engine."""

    def test_perfect_classifier(self) -> None:
        """All positives found, no negatives found => F1=1.0."""
        counts = _EvalCounts(pos_hits=10, pos_total=10, neg_hits=0, neg_total=10)
        assert _f1_from_counts(counts) == pytest.approx(1.0)

    def test_zero_recall(self) -> None:
        """No positives found => F1=0.0."""
        counts = _EvalCounts(pos_hits=0, pos_total=10, neg_hits=5, neg_total=10)
        assert _f1_from_counts(counts) == 0.0

    def test_zero_recall_and_zero_precision(self) -> None:
        """No positives, no negatives => F1=0.0."""
        counts = _EvalCounts(pos_hits=0, pos_total=0, neg_hits=0, neg_total=0)
        assert _f1_from_counts(counts) == 0.0

    def test_no_negatives(self) -> None:
        """When neg_total=0, precision=1.0 (no FP possible)."""
        # tp=8, fp=0, fn=2 => precision=1.0, recall=0.8
        # F1 = 2*1.0*0.8/(1.0+0.8) = 1.6/1.8
        counts = _EvalCounts(pos_hits=8, pos_total=10, neg_hits=0, neg_total=0)
        expected = 2 * 1.0 * 0.8 / (1.0 + 0.8)
        assert _f1_from_counts(counts) == pytest.approx(expected)

    def test_high_false_positives(self) -> None:
        """All negatives found => low precision => low F1."""
        # tp=8, fp=10, fn=2, tn=0 => precision=8/18, recall=0.8
        counts = _EvalCounts(pos_hits=8, pos_total=10, neg_hits=10, neg_total=10)
        precision = 8 / 18
        recall = 0.8
        expected = 2 * precision * recall / (precision + recall)
        assert _f1_from_counts(counts) == pytest.approx(expected)

    def test_moderate_values(self) -> None:
        """tp=7, fp=2, fn=3, tn=8 => precision=7/9, recall=0.7."""
        counts = _EvalCounts(pos_hits=7, pos_total=10, neg_hits=2, neg_total=10)
        precision = 7 / 9
        recall = 0.7
        expected = 2 * precision * recall / (precision + recall)
        assert _f1_from_counts(counts) == pytest.approx(expected)


class TestCollectCombineNodes:
    """_collect_combine_nodes identifies binary (combine) nodes."""

    def test_single_leaf_no_combine(self) -> None:
        tree = {"id": "s1", "searchName": "A"}
        assert _collect_combine_nodes(tree) == []

    def test_single_combine(self) -> None:
        tree = {
            "id": "root",
            "operator": "INTERSECT",
            "primaryInput": {"id": "s1", "searchName": "A"},
            "secondaryInput": {"id": "s2", "searchName": "B"},
        }
        nodes = _collect_combine_nodes(tree)
        assert len(nodes) == 1
        assert _node_id(nodes[0]) == "root"

    def test_nested_combines(self) -> None:
        tree = {
            "id": "root",
            "operator": "UNION",
            "primaryInput": {
                "id": "mid",
                "operator": "INTERSECT",
                "primaryInput": {"id": "s1", "searchName": "A"},
                "secondaryInput": {"id": "s2", "searchName": "B"},
            },
            "secondaryInput": {"id": "s3", "searchName": "C"},
        }
        nodes = _collect_combine_nodes(tree)
        assert len(nodes) == 2
        ids = {_node_id(n) for n in nodes}
        assert ids == {"root", "mid"}

    def test_transform_node_not_combine(self) -> None:
        """Transform (unary) nodes have primaryInput but no secondaryInput."""
        tree = {
            "id": "root",
            "operator": "UNION",
            "primaryInput": {
                "id": "transform",
                "searchName": "GenesByOrthologs",
                "primaryInput": {"id": "s1", "searchName": "GeneByTaxon"},
            },
            "secondaryInput": {"id": "s2", "searchName": "B"},
        }
        nodes = _collect_combine_nodes(tree)
        assert len(nodes) == 1
        assert _node_id(nodes[0]) == "root"


class TestBuildSubtreeWithOperator:
    """_build_subtree_with_operator clones a subtree with a new operator."""

    def test_changes_operator(self) -> None:
        combine = {
            "id": "root",
            "operator": "INTERSECT",
            "primaryInput": {"id": "s1", "searchName": "A"},
            "secondaryInput": {"id": "s2", "searchName": "B"},
        }
        result = _build_subtree_with_operator(combine, "UNION")
        assert result["operator"] == "UNION"
        assert result["id"] == "root"

    def test_does_not_mutate_original(self) -> None:
        combine = {
            "id": "root",
            "operator": "INTERSECT",
            "primaryInput": {"id": "s1", "searchName": "A"},
            "secondaryInput": {"id": "s2", "searchName": "B"},
        }
        _build_subtree_with_operator(combine, "UNION")
        assert combine["operator"] == "INTERSECT"

    def test_deep_copy_subtree(self) -> None:
        """Modifying the result should not affect the original subtree."""
        combine = {
            "id": "root",
            "operator": "INTERSECT",
            "primaryInput": {"id": "s1", "searchName": "A", "params": {"x": 1}},
            "secondaryInput": {"id": "s2", "searchName": "B"},
        }
        result = _build_subtree_with_operator(combine, "UNION")
        # Modify nested structure in result
        pi = result["primaryInput"]
        assert isinstance(pi, dict)
        pi_params = pi.get("params")
        assert isinstance(pi_params, dict)
        pi_params["x"] = 999

        # Original should be unchanged
        orig_pi = combine["primaryInput"]
        assert isinstance(orig_pi, dict)
        assert orig_pi["params"]["x"] == 1  # type: ignore[index]


class TestNodeId:
    """_node_id extracts the node identifier."""

    def test_id_field(self) -> None:
        assert _node_id({"id": "s1"}) == "s1"

    def test_search_name_fallback(self) -> None:
        assert _node_id({"searchName": "GeneByTaxon"}) == "GeneByTaxon"

    def test_both_prefers_id(self) -> None:
        assert _node_id({"id": "s1", "searchName": "GeneByTaxon"}) == "s1"

    def test_neither_returns_question_mark(self) -> None:
        assert _node_id({}) == "?"

    def test_non_string_id(self) -> None:
        """Non-string IDs are converted via str()."""
        assert _node_id({"id": 42}) == "42"
