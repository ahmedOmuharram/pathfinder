"""Edge-case tests for metrics.py — division by zero, edge cases, NaN.

Covers areas NOT tested by the existing test_experiment_metrics.py:
- compute_confusion_matrix with hits > totals (overflow scenario)
- compute_metrics with only positives, only negatives
- metrics_from_control_result with float values, nested None
- MCC with extreme values (one quadrant zero)
- Youdens J range verification
- NPV / FPR / FNR correctness
"""

import math

import pytest

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


class TestComputeConfusionMatrixEdgeCases:
    """Edge cases for confusion matrix computation."""

    def test_only_positives_no_negatives(self) -> None:
        """When there are no negative controls at all."""
        cm = compute_confusion_matrix(
            positive_hits=5,
            total_positives=10,
            negative_hits=0,
            total_negatives=0,
        )
        assert cm.true_positives == 5
        assert cm.false_negatives == 5
        assert cm.false_positives == 0
        assert cm.true_negatives == 0

    def test_only_negatives_no_positives(self) -> None:
        """When there are no positive controls at all."""
        cm = compute_confusion_matrix(
            positive_hits=0,
            total_positives=0,
            negative_hits=3,
            total_negatives=10,
        )
        assert cm.true_positives == 0
        assert cm.false_negatives == 0
        assert cm.false_positives == 3
        assert cm.true_negatives == 7

    def test_hits_exceed_totals_clamped(self) -> None:
        """When positive_hits > total_positives, FN is clamped to 0.

        This can happen if the intersection API returns more hits than
        the provided controls count (e.g. due to ID aliasing).
        """
        cm = compute_confusion_matrix(
            positive_hits=15,
            total_positives=10,
            negative_hits=0,
            total_negatives=5,
        )
        # tp is 15 (not clamped), fn is max(10-15, 0) = 0
        assert cm.true_positives == 15
        assert cm.false_negatives == 0

    def test_large_values(self) -> None:
        cm = compute_confusion_matrix(
            positive_hits=50000,
            total_positives=100000,
            negative_hits=1000,
            total_negatives=500000,
        )
        assert cm.true_positives == 50000
        assert cm.false_negatives == 50000
        assert cm.false_positives == 1000
        assert cm.true_negatives == 499000


class TestComputeMetricsEdgeCases:
    """Edge cases for compute_metrics."""

    def test_only_true_positives(self) -> None:
        """All predictions are TP — no negatives exist."""
        cm = ConfusionMatrix(
            true_positives=10, false_positives=0, true_negatives=0, false_negatives=0
        )
        m = compute_metrics(cm)
        assert m.sensitivity == 1.0
        assert m.specificity == 0.0  # no negatives: TN/(TN+FP) = 0/0 = 0
        assert m.precision == 1.0
        assert m.f1_score == 1.0

    def test_only_true_negatives(self) -> None:
        """All predictions are TN — no positives exist."""
        cm = ConfusionMatrix(
            true_positives=0, false_positives=0, true_negatives=10, false_negatives=0
        )
        m = compute_metrics(cm)
        assert m.sensitivity == 0.0  # no positives: TP/(TP+FN) = 0/0 = 0
        assert m.specificity == 1.0
        assert m.precision == 0.0  # TP/(TP+FP) = 0/0 = 0

    def test_only_false_positives(self) -> None:
        cm = ConfusionMatrix(
            true_positives=0, false_positives=10, true_negatives=0, false_negatives=0
        )
        m = compute_metrics(cm)
        assert m.sensitivity == 0.0
        assert m.specificity == 0.0
        assert m.precision == 0.0
        assert m.false_positive_rate == 1.0

    def test_only_false_negatives(self) -> None:
        cm = ConfusionMatrix(
            true_positives=0, false_positives=0, true_negatives=0, false_negatives=10
        )
        m = compute_metrics(cm)
        assert m.sensitivity == 0.0
        assert m.false_negative_rate == 1.0

    def test_mcc_with_one_zero_quadrant(self) -> None:
        """MCC denominator becomes 0 when one of the four sums is zero.

        E.g. TP=5, FP=0, TN=5, FN=5 -> (TP+FP)=5, (TP+FN)=10, (TN+FP)=5, (TN+FN)=10
        -> denom = sqrt(5*10*5*10) = sqrt(2500) = 50 > 0 -> OK

        But TP=0, FP=0 -> (TP+FP)=0 -> denom=0 -> MCC=0
        """
        cm = ConfusionMatrix(
            true_positives=0, false_positives=0, true_negatives=5, false_negatives=5
        )
        m = compute_metrics(cm)
        assert m.mcc == 0.0  # denom is 0

    def test_npv_correctness(self) -> None:
        """Negative predictive value = TN / (TN + FN)."""
        cm = ConfusionMatrix(
            true_positives=8, false_positives=2, true_negatives=18, false_negatives=2
        )
        m = compute_metrics(cm)
        expected_npv = 18 / (18 + 2)
        assert m.negative_predictive_value == pytest.approx(expected_npv)

    def test_fpr_equals_1_minus_specificity(self) -> None:
        cm = ConfusionMatrix(
            true_positives=7, false_positives=3, true_negatives=17, false_negatives=3
        )
        m = compute_metrics(cm)
        assert m.false_positive_rate == pytest.approx(1.0 - m.specificity)

    def test_fnr_equals_1_minus_sensitivity(self) -> None:
        cm = ConfusionMatrix(
            true_positives=7, false_positives=3, true_negatives=17, false_negatives=3
        )
        m = compute_metrics(cm)
        assert m.false_negative_rate == pytest.approx(1.0 - m.sensitivity)

    def test_youdens_j_range(self) -> None:
        """Youden's J should be in [-1, 1]."""
        cm = ConfusionMatrix(
            true_positives=3, false_positives=7, true_negatives=13, false_negatives=7
        )
        m = compute_metrics(cm)
        assert -1.0 <= m.youdens_j <= 1.0

    def test_youdens_j_equals_sens_plus_spec_minus_one(self) -> None:
        cm = ConfusionMatrix(
            true_positives=8, false_positives=2, true_negatives=18, false_negatives=2
        )
        m = compute_metrics(cm)
        assert m.youdens_j == pytest.approx(m.sensitivity + m.specificity - 1.0)

    def test_f1_is_harmonic_mean(self) -> None:
        """F1 = 2 * P * R / (P + R)."""
        cm = ConfusionMatrix(
            true_positives=6, false_positives=4, true_negatives=16, false_negatives=4
        )
        m = compute_metrics(cm)
        expected_f1 = 2 * m.precision * m.sensitivity / (m.precision + m.sensitivity)
        assert m.f1_score == pytest.approx(expected_f1)

    def test_mcc_perfect_classifier(self) -> None:
        cm = ConfusionMatrix(
            true_positives=10, false_positives=0, true_negatives=10, false_negatives=0
        )
        m = compute_metrics(cm)
        assert m.mcc == pytest.approx(1.0)

    def test_mcc_inverse_classifier(self) -> None:
        """Perfectly wrong classifier: all positives predicted as negative and vice versa."""
        cm = ConfusionMatrix(
            true_positives=0, false_positives=10, true_negatives=0, false_negatives=10
        )
        m = compute_metrics(cm)
        assert m.mcc == pytest.approx(-1.0)

    def test_no_nan_in_any_metric(self) -> None:
        """Exhaustive check: no NaN in any metric field for all-zero confusion matrix."""
        cm = ConfusionMatrix(
            true_positives=0, false_positives=0, true_negatives=0, false_negatives=0
        )
        m = compute_metrics(cm)
        for field_name in (
            "sensitivity",
            "specificity",
            "precision",
            "negative_predictive_value",
            "false_positive_rate",
            "false_negative_rate",
            "f1_score",
            "mcc",
            "balanced_accuracy",
            "youdens_j",
        ):
            value = getattr(m, field_name)
            assert not math.isnan(value), f"{field_name} is NaN"
            assert math.isfinite(value), f"{field_name} is not finite"


class TestMetricsFromControlResultEdgeCases:
    """metrics_from_control_result with unusual inputs."""

    def test_int_counts(self) -> None:
        """Standard int counts should produce correct metrics."""
        result = ControlTestResult(
            positive=ControlSetData(intersection_count=8, controls_count=10),
            negative=ControlSetData(intersection_count=3, controls_count=20),
            target=ControlTargetData(estimated_size=100),
        )
        m = metrics_from_control_result(result)
        assert m.confusion_matrix.true_positives == 8
        assert m.total_results == 100

    def test_zero_counts_default(self) -> None:
        """Default ControlSetData has zero counts."""
        result = ControlTestResult(
            positive=ControlSetData(),
            negative=ControlSetData(),
            target=ControlTargetData(),
        )
        m = metrics_from_control_result(result)
        assert m.confusion_matrix.true_positives == 0
        assert m.total_results == 0

    def test_positive_none_negative_present(self) -> None:
        """When positive is None but negative has data."""
        result = ControlTestResult(
            positive=None,
            negative=ControlSetData(intersection_count=5, controls_count=20),
            target=ControlTargetData(estimated_size=50),
        )
        m = metrics_from_control_result(result)
        assert m.confusion_matrix.true_positives == 0
        assert m.confusion_matrix.false_positives == 5
        assert m.confusion_matrix.true_negatives == 15

    def test_empty_control_test_result(self) -> None:
        result = ControlTestResult()
        m = metrics_from_control_result(result)
        assert m.confusion_matrix.true_positives == 0
        assert m.confusion_matrix.false_positives == 0
        assert m.confusion_matrix.true_negatives == 0
        assert m.confusion_matrix.false_negatives == 0
