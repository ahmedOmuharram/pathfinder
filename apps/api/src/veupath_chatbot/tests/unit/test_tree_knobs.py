"""Tests for multi-step tree-knob optimization helpers.

Only tests pure-logic functions that don't require Optuna or WDK calls.
"""

import copy
import math

from veupath_chatbot.services.experiment.tree_knobs import (
    _apply_knobs_recursive,
    _select_metric,
)
from veupath_chatbot.services.experiment.types.metrics import (
    ConfusionMatrix,
    ExperimentMetrics,
)


def _make_metrics(
    *,
    tp: int = 8,
    fp: int = 2,
    fn: int = 2,
    tn: int = 18,
    precision: float = 0.8,
    recall: float = 0.8,
    specificity: float = 0.9,
) -> ExperimentMetrics:
    return ExperimentMetrics(
        confusion_matrix=ConfusionMatrix(
            true_positives=tp,
            false_positives=fp,
            true_negatives=tn,
            false_negatives=fn,
        ),
        sensitivity=recall,
        specificity=specificity,
        precision=precision,
        f1_score=2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0,
        mcc=_mcc(tp, fp, fn, tn),
        balanced_accuracy=(recall + specificity) / 2,
    )


def _mcc(tp: int, fp: int, fn: int, tn: int) -> float:
    denom = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    if denom == 0:
        return 0.0
    return (tp * tn - fp * fn) / denom


class TestApplyKnobsRecursive:
    def test_applies_operator_to_matching_node(self) -> None:
        tree = {
            "id": "combine1",
            "operator": "INTERSECT",
            "primaryInput": {"id": "leaf1", "parameters": {"score": "0.5"}},
            "secondaryInput": {"id": "leaf2", "parameters": {"score": "0.8"}},
        }
        _apply_knobs_recursive(tree, {}, {"combine1": "UNION"})
        assert tree["operator"] == "UNION"

    def test_applies_threshold_to_matching_leaf(self) -> None:
        tree = {
            "id": "leaf1",
            "parameters": {"score": "0.5", "evalue": "1e-5"},
        }
        _apply_knobs_recursive(tree, {"leaf1:score": 0.9}, {})
        assert tree["parameters"]["score"] == "0.9"
        assert tree["parameters"]["evalue"] == "1e-5"  # unchanged

    def test_recursive_into_children(self) -> None:
        tree = {
            "id": "root",
            "operator": "INTERSECT",
            "primaryInput": {
                "id": "leaf1",
                "parameters": {"score": "0.5"},
            },
            "secondaryInput": {
                "id": "leaf2",
                "parameters": {"evalue": "1e-3"},
            },
        }
        _apply_knobs_recursive(
            tree,
            {"leaf1:score": 0.7, "leaf2:evalue": 1e-6},
            {"root": "MINUS"},
        )
        assert tree["operator"] == "MINUS"
        assert tree["primaryInput"]["parameters"]["score"] == "0.7"
        assert tree["secondaryInput"]["parameters"]["evalue"] == "1e-06"

    def test_no_matching_nodes(self) -> None:
        tree = {
            "id": "leaf1",
            "parameters": {"score": "0.5"},
        }
        original = copy.deepcopy(tree)
        _apply_knobs_recursive(tree, {"other:score": 0.9}, {"other": "UNION"})
        assert tree == original

    def test_missing_parameters(self) -> None:
        """Node without parameters dict should not crash."""
        tree = {"id": "leaf1"}
        _apply_knobs_recursive(tree, {"leaf1:score": 0.5}, {})
        assert "parameters" not in tree

    def test_deeply_nested_tree(self) -> None:
        tree = {
            "id": "root",
            "operator": "UNION",
            "primaryInput": {
                "id": "mid",
                "operator": "INTERSECT",
                "primaryInput": {
                    "id": "deep_leaf",
                    "parameters": {"cutoff": "10"},
                },
                "secondaryInput": {
                    "id": "deep_leaf2",
                    "parameters": {"threshold": "0.01"},
                },
            },
            "secondaryInput": {
                "id": "side_leaf",
                "parameters": {"pvalue": "0.05"},
            },
        }
        _apply_knobs_recursive(
            tree,
            {"deep_leaf:cutoff": 20, "side_leaf:pvalue": 0.01},
            {"mid": "MINUS"},
        )
        assert tree["primaryInput"]["operator"] == "MINUS"
        assert tree["primaryInput"]["primaryInput"]["parameters"]["cutoff"] == "20"
        assert tree["secondaryInput"]["parameters"]["pvalue"] == "0.01"


class TestSelectMetric:
    def _base_metrics(self) -> ExperimentMetrics:
        return _make_metrics()

    def test_precision_objective(self) -> None:
        assert (
            _select_metric(
                "precision_at_50", metrics=self._base_metrics(), enrichment=2.0
            )
            == 0.8
        )

    def test_recall_objective(self) -> None:
        assert (
            _select_metric("recall_at_50", metrics=self._base_metrics(), enrichment=2.0)
            == 0.8
        )

    def test_sensitivity_objective(self) -> None:
        assert (
            _select_metric("sensitivity", metrics=self._base_metrics(), enrichment=2.0)
            == 0.8
        )

    def test_enrichment_objective(self) -> None:
        assert (
            _select_metric(
                "enrichment_at_50", metrics=self._base_metrics(), enrichment=2.0
            )
            == 2.0
        )

    def test_specificity_objective(self) -> None:
        assert (
            _select_metric("specificity", metrics=self._base_metrics(), enrichment=2.0)
            == 0.9
        )

    def test_balanced_accuracy_objective(self) -> None:
        result = _select_metric(
            "balanced_accuracy", metrics=self._base_metrics(), enrichment=2.0
        )
        assert result == (0.8 + 0.9) / 2

    def test_f1_objective(self) -> None:
        result = _select_metric("f1", metrics=self._base_metrics(), enrichment=2.0)
        expected = 2 * 0.8 * 0.8 / (0.8 + 0.8)
        assert abs(result - expected) < 1e-10

    def test_f1_zero_denom(self) -> None:
        m = _make_metrics(precision=0.0, recall=0.0)
        assert _select_metric("f1", metrics=m, enrichment=2.0) == 0.0

    def test_mcc_objective(self) -> None:
        result = _select_metric("mcc", metrics=self._base_metrics(), enrichment=2.0)
        denom = math.sqrt(10 * 10 * 20 * 20)
        expected = (8 * 18 - 2 * 2) / denom
        assert abs(result - expected) < 1e-10

    def test_mcc_zero_denom(self) -> None:
        m = _make_metrics(
            tp=0, fp=0, fn=0, tn=0, precision=0.0, recall=0.0, specificity=0.0
        )
        assert _select_metric("mcc", metrics=m, enrichment=2.0) == 0.0

    def test_unknown_objective_defaults_to_precision(self) -> None:
        assert (
            _select_metric(
                "unknown_metric", metrics=self._base_metrics(), enrichment=2.0
            )
            == 0.8
        )

    def test_case_insensitive(self) -> None:
        assert (
            _select_metric(
                "PRECISION_AT_50", metrics=self._base_metrics(), enrichment=2.0
            )
            == 0.8
        )
        assert (
            _select_metric(
                "Recall_at_100", metrics=self._base_metrics(), enrichment=2.0
            )
            == 0.8
        )
