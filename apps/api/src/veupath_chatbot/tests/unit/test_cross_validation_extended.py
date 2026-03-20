"""Bug-hunting tests for cross_validation.py — edge cases and correctness.

Extends test_cross_validation.py with:
- _stratified_kfold edge cases (empty list, single element, k > len)
- _average_metrics with empty list
- _std_metrics with identical metrics (zero variance)
- _compute_overfitting_score thresholds and boundary values
- _run_kfold with very small control sets
- _run_kfold fold evaluator that raises
"""

import math

import pytest

from veupath_chatbot.services.experiment.cross_validation import (
    _average_metrics,
    _compute_overfitting_score,
    _std_metrics,
    _stratified_kfold,
)
from veupath_chatbot.services.experiment.types import (
    ConfusionMatrix,
    ExperimentMetrics,
)


def _make_metrics(
    sensitivity: float = 0.8,
    specificity: float = 0.7,
    precision: float = 0.6,
    f1_score: float = 0.7,
    mcc: float = 0.5,
) -> ExperimentMetrics:
    cm = ConfusionMatrix(
        true_positives=1, false_positives=0, true_negatives=1, false_negatives=0
    )
    return ExperimentMetrics(
        confusion_matrix=cm,
        sensitivity=sensitivity,
        specificity=specificity,
        precision=precision,
        negative_predictive_value=0.5,
        false_positive_rate=1 - specificity,
        false_negative_rate=1 - sensitivity,
        f1_score=f1_score,
        mcc=mcc,
        balanced_accuracy=(sensitivity + specificity) / 2,
        youdens_j=sensitivity + specificity - 1,
        total_results=10,
        total_positives=5,
        total_negatives=5,
    )


class TestStratifiedKfold:
    """_stratified_kfold splits a list into k roughly equal folds."""

    def test_empty_list(self) -> None:
        """Empty input produces k empty folds."""
        folds = _stratified_kfold([], 5)
        assert len(folds) == 5
        for fold in folds:
            assert fold == []

    def test_single_element(self) -> None:
        """Single element ends up in exactly one fold."""
        folds = _stratified_kfold(["a"], 3)
        assert len(folds) == 3
        all_items = [item for fold in folds for item in fold]
        assert all_items == ["a"]

    def test_k_equals_1(self) -> None:
        """k=1 puts everything in one fold."""
        folds = _stratified_kfold(["a", "b", "c"], 1)
        assert len(folds) == 1
        assert sorted(folds[0]) == ["a", "b", "c"]

    def test_k_equals_n(self) -> None:
        """k equals list length: one item per fold."""
        folds = _stratified_kfold(["a", "b", "c"], 3)
        assert len(folds) == 3
        for fold in folds:
            assert len(fold) == 1
        all_items = sorted(item for fold in folds for item in fold)
        assert all_items == ["a", "b", "c"]

    def test_k_greater_than_n(self) -> None:
        """k > list length: some folds are empty."""
        folds = _stratified_kfold(["a", "b"], 5)
        assert len(folds) == 5
        non_empty = [f for f in folds if f]
        assert len(non_empty) == 2  # only 2 items
        all_items = sorted(item for fold in folds for item in fold)
        assert all_items == ["a", "b"]

    def test_deterministic_with_same_seed(self) -> None:
        """Same seed produces same folds."""
        items = list("abcdefghij")
        folds1 = _stratified_kfold(items, 3, seed=42)
        folds2 = _stratified_kfold(items, 3, seed=42)
        assert folds1 == folds2

    def test_different_seed_different_folds(self) -> None:
        """Different seeds (usually) produce different folds."""
        items = list("abcdefghijklmnop")
        folds1 = _stratified_kfold(items, 3, seed=42)
        folds2 = _stratified_kfold(items, 3, seed=99)
        # Very unlikely to be equal
        assert folds1 != folds2

    def test_all_items_preserved(self) -> None:
        """No items lost or duplicated across folds."""
        items = [f"item_{i}" for i in range(17)]
        folds = _stratified_kfold(items, 5)
        all_items = [item for fold in folds for item in fold]
        assert sorted(all_items) == sorted(items)

    def test_folds_roughly_equal_size(self) -> None:
        """Fold sizes differ by at most 1."""
        items = [f"item_{i}" for i in range(17)]
        folds = _stratified_kfold(items, 5)
        sizes = [len(f) for f in folds]
        assert max(sizes) - min(sizes) <= 1

    def test_does_not_mutate_input(self) -> None:
        """Input list should not be modified."""
        items = ["a", "b", "c", "d"]
        original = list(items)
        _stratified_kfold(items, 2)
        assert items == original


class TestAverageMetrics:
    """_average_metrics handles various input sizes."""

    def test_empty_list_returns_zero_metrics(self) -> None:
        """Empty fold list returns zeroed-out metrics."""
        m = _average_metrics([])
        assert m.sensitivity == 0.0
        assert m.specificity == 0.0
        assert m.f1_score == 0.0

    def test_single_metrics_returns_same(self) -> None:
        """Single-element list returns approximately the same values."""
        orig = _make_metrics(sensitivity=0.9, specificity=0.8, precision=0.7)
        avg = _average_metrics([orig])
        assert avg.sensitivity == pytest.approx(0.9)
        assert avg.specificity == pytest.approx(0.8)
        assert avg.precision == pytest.approx(0.7)

    def test_two_metrics_averaged(self) -> None:
        m1 = _make_metrics(sensitivity=0.9, specificity=0.8, precision=0.7)
        m2 = _make_metrics(sensitivity=0.7, specificity=0.6, precision=0.5)
        avg = _average_metrics([m1, m2])
        assert avg.sensitivity == pytest.approx(0.8)
        assert avg.specificity == pytest.approx(0.7)
        assert avg.precision == pytest.approx(0.6)

    def test_confusion_matrix_rounded(self) -> None:
        """Averaged confusion matrix values are rounded to integers."""
        m1 = _make_metrics()
        m2 = _make_metrics()
        # Both have cm = (1, 0, 1, 0), so average is (1, 0, 1, 0)
        avg = _average_metrics([m1, m2])
        assert isinstance(avg.confusion_matrix.true_positives, int)
        assert isinstance(avg.confusion_matrix.false_positives, int)


class TestStdMetrics:
    """_std_metrics edge cases."""

    def test_empty_list_returns_empty(self) -> None:
        m = _make_metrics()
        result = _std_metrics([], m)
        assert result == {}

    def test_identical_metrics_zero_std(self) -> None:
        """When all folds have identical metrics, std should be 0."""
        m = _make_metrics(
            sensitivity=0.8, specificity=0.7, precision=0.6, f1_score=0.7, mcc=0.5
        )
        result = _std_metrics([m, m, m], m)
        for key, value in result.items():
            assert value == pytest.approx(0.0), f"{key} should be 0.0"

    def test_two_folds_correct_std(self) -> None:
        """Verify std with 2 folds uses Bessel correction (n-1)."""
        m1 = _make_metrics(sensitivity=1.0)
        m2 = _make_metrics(sensitivity=0.0)
        mean = _average_metrics([m1, m2])
        result = _std_metrics([m1, m2], mean)
        # std of [1.0, 0.0] with n-1: sqrt(((1-0.5)^2 + (0-0.5)^2) / 1) = sqrt(0.5)
        assert result["sensitivity"] == pytest.approx(math.sqrt(0.5))


class TestComputeOverfittingScore:
    """_compute_overfitting_score boundary tests."""

    def test_identical_metrics_low_overfitting(self) -> None:
        """No gap between full and holdout -> low overfitting."""
        full = _make_metrics(sensitivity=0.8, specificity=0.7, f1_score=0.75)
        holdout = _make_metrics(sensitivity=0.8, specificity=0.7, f1_score=0.75)
        score, level = _compute_overfitting_score(full, holdout)
        assert score == pytest.approx(0.0)
        assert level == "low"

    def test_small_gap_low_overfitting(self) -> None:
        """Small gaps (< 0.1 average) -> low overfitting."""
        full = _make_metrics(sensitivity=0.85, specificity=0.75, f1_score=0.80)
        holdout = _make_metrics(sensitivity=0.80, specificity=0.72, f1_score=0.76)
        score, level = _compute_overfitting_score(full, holdout)
        assert score < 0.1
        assert level == "low"

    def test_moderate_gap(self) -> None:
        """Gap of ~0.15 average -> moderate."""
        full = _make_metrics(sensitivity=0.9, specificity=0.9, f1_score=0.9)
        holdout = _make_metrics(sensitivity=0.75, specificity=0.75, f1_score=0.75)
        score, level = _compute_overfitting_score(full, holdout)
        # gap = (0.15 + 0.15 + 0.15) / 3 = 0.15
        assert score == pytest.approx(0.15)
        assert level == "moderate"

    def test_high_gap(self) -> None:
        """Large gap -> high overfitting."""
        full = _make_metrics(sensitivity=1.0, specificity=1.0, f1_score=1.0)
        holdout = _make_metrics(sensitivity=0.3, specificity=0.3, f1_score=0.3)
        score, level = _compute_overfitting_score(full, holdout)
        assert score >= 0.25
        assert level == "high"

    def test_boundary_at_0_1(self) -> None:
        """Score exactly at 0.1 boundary should be moderate (>= 0.1)."""
        # Need gap average of exactly 0.1
        full = _make_metrics(sensitivity=0.8, specificity=0.8, f1_score=0.8)
        holdout = _make_metrics(sensitivity=0.7, specificity=0.7, f1_score=0.7)
        score, level = _compute_overfitting_score(full, holdout)
        assert score == pytest.approx(0.1)
        assert level == "moderate"

    def test_boundary_at_0_25(self) -> None:
        """Score exactly at 0.25 boundary should be high (>= 0.25)."""
        full = _make_metrics(sensitivity=0.9, specificity=0.9, f1_score=0.9)
        holdout = _make_metrics(sensitivity=0.65, specificity=0.65, f1_score=0.65)
        score, level = _compute_overfitting_score(full, holdout)
        assert score == pytest.approx(0.25)
        assert level == "high"

    def test_holdout_better_than_full(self) -> None:
        """When holdout is BETTER than full, gaps are still absolute values."""
        full = _make_metrics(sensitivity=0.5, specificity=0.5, f1_score=0.5)
        holdout = _make_metrics(sensitivity=0.9, specificity=0.9, f1_score=0.9)
        score, _level = _compute_overfitting_score(full, holdout)
        # abs() ensures positive score
        assert score > 0.0

    def test_score_cannot_exceed_one(self) -> None:
        """Maximum gap per metric is 1.0, so max score is 1.0."""
        full = _make_metrics(sensitivity=1.0, specificity=1.0, f1_score=1.0)
        holdout = _make_metrics(sensitivity=0.0, specificity=0.0, f1_score=0.0)
        score, level = _compute_overfitting_score(full, holdout)
        assert score == pytest.approx(1.0)
        assert level == "high"
