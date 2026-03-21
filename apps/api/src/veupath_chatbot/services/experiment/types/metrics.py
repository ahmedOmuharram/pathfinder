"""Classification metrics for the Experiment Lab."""

from pydantic import ConfigDict, Field

from veupath_chatbot.platform.pydantic_base import CamelModel, RoundedFloat


class ConfusionMatrix(CamelModel):
    """2x2 confusion matrix counts."""

    model_config = ConfigDict(frozen=True)

    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int


class ExperimentMetrics(CamelModel):
    """Full classification metrics derived from a confusion matrix."""

    model_config = ConfigDict(frozen=True)

    confusion_matrix: ConfusionMatrix
    sensitivity: RoundedFloat
    specificity: RoundedFloat
    precision: RoundedFloat
    f1_score: RoundedFloat
    mcc: RoundedFloat
    balanced_accuracy: RoundedFloat
    # Fields below may be absent in older persisted data.
    negative_predictive_value: RoundedFloat = 0.0
    false_positive_rate: RoundedFloat = 0.0
    false_negative_rate: RoundedFloat = 0.0
    youdens_j: RoundedFloat = 0.0
    total_results: int = 0
    total_positives: int = 0
    total_negatives: int = 0


class GeneInfo(CamelModel):
    """Minimal gene metadata."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str | None = None
    organism: str | None = None
    product: str | None = None


class FoldMetrics(CamelModel):
    """Metrics for a single cross-validation fold."""

    model_config = ConfigDict(frozen=True)

    fold_index: int
    metrics: ExperimentMetrics
    positive_control_ids: list[str] = Field(default_factory=list)
    negative_control_ids: list[str] = Field(default_factory=list)


class CrossValidationResult(CamelModel):
    """Aggregated cross-validation result."""

    model_config = ConfigDict(frozen=True)

    k: int
    folds: list[FoldMetrics]
    mean_metrics: ExperimentMetrics
    std_metrics: dict[str, float] = Field(default_factory=dict)
    overfitting_score: RoundedFloat = 0.0
    overfitting_level: str = "low"
