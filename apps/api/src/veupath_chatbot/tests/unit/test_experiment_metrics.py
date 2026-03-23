"""Unit tests for experiment metrics computation."""

import math

from veupath_chatbot.services.experiment.metrics import (
    compute_confusion_matrix,
    compute_metrics,
    metrics_from_control_result,
)
from veupath_chatbot.services.experiment.types import ConfusionMatrix
from veupath_chatbot.services.experiment.types.control_result import (
    ControlSetData,
    ControlTargetData,
    ControlTestResult,
)


class TestComputeConfusionMatrix:
    def test_basic_counts(self) -> None:
        cm = compute_confusion_matrix(
            positive_hits=8,
            total_positives=10,
            negative_hits=3,
            total_negatives=20,
        )
        assert cm.true_positives == 8
        assert cm.false_negatives == 2
        assert cm.false_positives == 3
        assert cm.true_negatives == 17

    def test_perfect_classifier(self) -> None:
        cm = compute_confusion_matrix(
            positive_hits=10,
            total_positives=10,
            negative_hits=0,
            total_negatives=10,
        )
        assert cm.true_positives == 10
        assert cm.false_negatives == 0
        assert cm.false_positives == 0
        assert cm.true_negatives == 10

    def test_worst_classifier(self) -> None:
        cm = compute_confusion_matrix(
            positive_hits=0,
            total_positives=10,
            negative_hits=10,
            total_negatives=10,
        )
        assert cm.true_positives == 0
        assert cm.false_negatives == 10
        assert cm.false_positives == 10
        assert cm.true_negatives == 0

    def test_negative_counts_clamped_to_zero(self) -> None:
        cm = compute_confusion_matrix(
            positive_hits=15,
            total_positives=10,
            negative_hits=25,
            total_negatives=20,
        )
        assert cm.false_negatives == 0
        assert cm.true_negatives == 0

    def test_empty_controls(self) -> None:
        cm = compute_confusion_matrix(
            positive_hits=0,
            total_positives=0,
            negative_hits=0,
            total_negatives=0,
        )
        assert cm.true_positives == 0
        assert cm.false_positives == 0
        assert cm.true_negatives == 0
        assert cm.false_negatives == 0


class TestComputeMetrics:
    def test_perfect_metrics(self) -> None:
        cm = ConfusionMatrix(
            true_positives=10,
            false_positives=0,
            true_negatives=10,
            false_negatives=0,
        )
        m = compute_metrics(cm, total_results=20)
        assert m.sensitivity == 1.0
        assert m.specificity == 1.0
        assert m.precision == 1.0
        assert m.f1_score == 1.0
        assert m.mcc == 1.0
        assert m.balanced_accuracy == 1.0
        assert m.youdens_j == 1.0
        assert m.total_results == 20

    def test_zero_metrics_when_no_positives_found(self) -> None:
        cm = ConfusionMatrix(
            true_positives=0,
            false_positives=5,
            true_negatives=15,
            false_negatives=10,
        )
        m = compute_metrics(cm)
        assert m.sensitivity == 0.0
        assert m.precision == 0.0
        assert m.f1_score == 0.0

    def test_balanced_accuracy_is_mean(self) -> None:
        cm = ConfusionMatrix(
            true_positives=8,
            false_positives=3,
            true_negatives=17,
            false_negatives=2,
        )
        m = compute_metrics(cm)
        expected_ba = (m.sensitivity + m.specificity) / 2
        assert abs(m.balanced_accuracy - expected_ba) < 1e-10

    def test_mcc_range(self) -> None:
        cm = ConfusionMatrix(
            true_positives=7,
            false_positives=5,
            true_negatives=15,
            false_negatives=3,
        )
        m = compute_metrics(cm)
        assert -1.0 <= m.mcc <= 1.0

    def test_all_zeros_no_division_error(self) -> None:
        cm = ConfusionMatrix(
            true_positives=0,
            false_positives=0,
            true_negatives=0,
            false_negatives=0,
        )
        m = compute_metrics(cm)
        assert m.sensitivity == 0.0
        assert m.specificity == 0.0
        assert m.precision == 0.0
        assert m.f1_score == 0.0
        assert m.mcc == 0.0
        assert not math.isnan(m.balanced_accuracy)

    def test_total_positives_and_negatives(self) -> None:
        cm = ConfusionMatrix(
            true_positives=8,
            false_positives=3,
            true_negatives=17,
            false_negatives=2,
        )
        m = compute_metrics(cm)
        assert m.total_positives == 10  # TP + FN
        assert m.total_negatives == 20  # TN + FP


class TestMetricsFromControlResult:
    def test_standard_result(self) -> None:
        result = ControlTestResult(
            positive=ControlSetData(intersection_count=8, controls_count=10),
            negative=ControlSetData(intersection_count=3, controls_count=20),
            target=ControlTargetData(result_count=100),
        )
        m = metrics_from_control_result(result)
        assert m.confusion_matrix.true_positives == 8
        assert m.confusion_matrix.false_positives == 3
        assert m.total_results == 100

    def test_missing_fields_default_to_zero(self) -> None:
        result = ControlTestResult()
        m = metrics_from_control_result(result)
        assert m.confusion_matrix.true_positives == 0
        assert m.total_results == 0

    def test_none_sections_default_to_zero(self) -> None:
        result = ControlTestResult(
            positive=None,
            negative=None,
        )
        m = metrics_from_control_result(result)
        assert m.confusion_matrix.true_positives == 0
