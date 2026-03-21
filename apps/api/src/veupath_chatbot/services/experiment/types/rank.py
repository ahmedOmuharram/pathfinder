"""Rank-based evaluation types for the Experiment Lab."""

from pydantic import ConfigDict, Field

from veupath_chatbot.platform.pydantic_base import CamelModel, RoundedFloat


class RankMetrics(CamelModel):
    """Rank-based evaluation metrics computed over an ordered result list."""

    model_config = ConfigDict(frozen=True)

    precision_at_k: dict[int, float] = Field(default_factory=dict)
    recall_at_k: dict[int, float] = Field(default_factory=dict)
    enrichment_at_k: dict[int, float] = Field(default_factory=dict)
    pr_curve: list[tuple[float, float]] = Field(default_factory=list)
    list_size_vs_recall: list[tuple[int, float]] = Field(default_factory=list)
    total_results: int = 0


class ConfidenceInterval(CamelModel):
    """Bootstrap confidence interval for a single metric."""

    model_config = ConfigDict(frozen=True)

    lower: RoundedFloat = 0.0
    mean: RoundedFloat = 0.0
    upper: RoundedFloat = 0.0
    std: RoundedFloat = 0.0


class NegativeSetVariant(CamelModel):
    """Rank metrics evaluated with an alternative negative control set."""

    model_config = ConfigDict(frozen=True)

    label: str
    rank_metrics: RankMetrics
    negative_count: int = 0


class BootstrapResult(CamelModel):
    """Robustness assessment via bootstrap resampling."""

    model_config = ConfigDict(frozen=True)

    n_iterations: int = 0
    metric_cis: dict[str, ConfidenceInterval] = Field(default_factory=dict)
    rank_metric_cis: dict[str, ConfidenceInterval] = Field(default_factory=dict)
    top_k_stability: RoundedFloat = 0.0
    negative_set_sensitivity: list[NegativeSetVariant] = Field(default_factory=list)
