"""Rank-based evaluation dataclasses for the Experiment Lab."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class RankMetrics:
    """Rank-based evaluation metrics computed over an ordered result list."""

    precision_at_k: dict[int, float] = field(default_factory=dict)
    recall_at_k: dict[int, float] = field(default_factory=dict)
    enrichment_at_k: dict[int, float] = field(default_factory=dict)
    pr_curve: list[tuple[float, float]] = field(default_factory=list)
    list_size_vs_recall: list[tuple[int, float]] = field(default_factory=list)
    total_results: int = 0


@dataclass(frozen=True, slots=True)
class ConfidenceInterval:
    """Bootstrap confidence interval for a single metric."""

    lower: float
    mean: float
    upper: float
    std: float


@dataclass(frozen=True, slots=True)
class NegativeSetVariant:
    """Rank metrics evaluated with an alternative negative control set."""

    label: str
    negative_count: int
    rank_metrics: RankMetrics


@dataclass(frozen=True, slots=True)
class BootstrapResult:
    """Robustness assessment via bootstrap resampling."""

    n_iterations: int
    metric_cis: dict[str, ConfidenceInterval] = field(default_factory=dict)
    rank_metric_cis: dict[str, ConfidenceInterval] = field(default_factory=dict)
    top_k_stability: float = 0.0
    negative_set_sensitivity: list[NegativeSetVariant] = field(default_factory=list)
