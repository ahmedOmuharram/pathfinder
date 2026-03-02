"""Classification metrics dataclasses for the Experiment Lab."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ConfusionMatrix:
    """2x2 confusion matrix counts."""

    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int


@dataclass(frozen=True, slots=True)
class ExperimentMetrics:
    """Full classification metrics derived from a confusion matrix."""

    confusion_matrix: ConfusionMatrix
    sensitivity: float
    specificity: float
    precision: float
    negative_predictive_value: float
    false_positive_rate: float
    false_negative_rate: float
    f1_score: float
    mcc: float
    balanced_accuracy: float
    youdens_j: float
    total_results: int
    total_positives: int
    total_negatives: int


@dataclass(frozen=True, slots=True)
class GeneInfo:
    """Minimal gene metadata."""

    id: str
    name: str | None = None
    organism: str | None = None
    product: str | None = None


@dataclass(frozen=True, slots=True)
class FoldMetrics:
    """Metrics for a single cross-validation fold."""

    fold_index: int
    metrics: ExperimentMetrics
    positive_control_ids: list[str]
    negative_control_ids: list[str]


@dataclass(frozen=True, slots=True)
class CrossValidationResult:
    """Aggregated cross-validation result."""

    k: int
    folds: list[FoldMetrics]
    mean_metrics: ExperimentMetrics
    std_metrics: dict[str, float]
    overfitting_score: float
    overfitting_level: str  # "low" | "moderate" | "high"
