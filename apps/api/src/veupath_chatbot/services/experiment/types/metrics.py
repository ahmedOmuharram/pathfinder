"""Classification metrics dataclasses for the Experiment Lab."""

from __future__ import annotations

from dataclasses import dataclass, field


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
    f1_score: float
    mcc: float
    balanced_accuracy: float
    # Fields below may be absent in older persisted data.
    negative_predictive_value: float = 0.0
    false_positive_rate: float = 0.0
    false_negative_rate: float = 0.0
    youdens_j: float = 0.0
    total_results: int = 0
    total_positives: int = 0
    total_negatives: int = 0


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
    positive_control_ids: list[str] = field(default_factory=list)
    negative_control_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class CrossValidationResult:
    """Aggregated cross-validation result."""

    k: int
    folds: list[FoldMetrics]
    mean_metrics: ExperimentMetrics
    std_metrics: dict[str, float] = field(default_factory=dict)
    overfitting_score: float = 0.0
    overfitting_level: str = "low"
