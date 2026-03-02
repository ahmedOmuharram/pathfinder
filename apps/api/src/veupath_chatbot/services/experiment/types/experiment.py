"""Experiment and ExperimentConfig dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field

from veupath_chatbot.platform.types import JSONObject, JSONValue
from veupath_chatbot.services.experiment.types.core import (
    ControlValueFormat,
    EnrichmentAnalysisType,
    ExperimentMode,
    ExperimentStatus,
    OptimizationObjective,
)
from veupath_chatbot.services.experiment.types.enrichment import EnrichmentResult
from veupath_chatbot.services.experiment.types.metrics import (
    CrossValidationResult,
    ExperimentMetrics,
    GeneInfo,
)
from veupath_chatbot.services.experiment.types.optimization import (
    OperatorKnob,
    OptimizationSpec,
    ThresholdKnob,
    TreeOptimizationResult,
)
from veupath_chatbot.services.experiment.types.rank import (
    BootstrapResult,
    RankMetrics,
)
from veupath_chatbot.services.experiment.types.step_analysis import StepAnalysisResult


@dataclass(slots=True)
class ExperimentConfig:
    """Full configuration for an experiment run.

    Supports three modes:

    * **single** (default): one search + parameters.
    * **multi-step**: a recursive ``step_tree`` of search/combine/transform nodes.
    * **import**: import an existing Pathfinder strategy by ``source_strategy_id``.
    """

    site_id: str
    record_type: str
    search_name: str
    parameters: JSONObject
    positive_controls: list[str]
    negative_controls: list[str]
    controls_search_name: str
    controls_param_name: str
    controls_value_format: ControlValueFormat = "newline"
    enable_cross_validation: bool = False
    k_folds: int = 5
    enrichment_types: list[EnrichmentAnalysisType] = field(default_factory=list)
    name: str = ""
    description: str = ""
    optimization_specs: list[OptimizationSpec] | None = None
    optimization_budget: int = 30
    optimization_objective: OptimizationObjective = "balanced_accuracy"
    parameter_display_values: dict[str, str] | None = None
    mode: ExperimentMode = "single"
    step_tree: JSONValue = None
    source_strategy_id: str | None = None
    optimization_target_step: str | None = None
    enable_step_analysis: bool = False
    step_analysis_phases: list[str] = field(
        default_factory=lambda: [
            "step_evaluation",
            "operator_comparison",
            "contribution",
            "sensitivity",
        ]
    )
    control_set_id: str | None = None
    threshold_knobs: list[ThresholdKnob] | None = None
    operator_knobs: list[OperatorKnob] | None = None
    tree_optimization_objective: str = "precision_at_50"
    tree_optimization_budget: int = 50
    max_list_size: int | None = None
    sort_attribute: str | None = None
    sort_direction: str = "ASC"
    parent_experiment_id: str | None = None


@dataclass(slots=True)
class BatchOrganismTarget:
    """Per-organism overrides for a cross-organism batch experiment."""

    organism: str
    positive_controls: list[str] = field(default_factory=list)
    negative_controls: list[str] = field(default_factory=list)


@dataclass(slots=True)
class BatchExperimentConfig:
    """Configuration for running the same search across multiple organisms."""

    base_config: ExperimentConfig
    organism_param_name: str
    target_organisms: list[BatchOrganismTarget] = field(default_factory=list)


@dataclass(slots=True)
class Experiment:
    """Full experiment with config and results."""

    id: str
    config: ExperimentConfig
    status: ExperimentStatus = "pending"
    metrics: ExperimentMetrics | None = None
    cross_validation: CrossValidationResult | None = None
    enrichment_results: list[EnrichmentResult] = field(default_factory=list)
    true_positive_genes: list[GeneInfo] = field(default_factory=list)
    false_negative_genes: list[GeneInfo] = field(default_factory=list)
    false_positive_genes: list[GeneInfo] = field(default_factory=list)
    true_negative_genes: list[GeneInfo] = field(default_factory=list)
    error: str | None = None
    total_time_seconds: float | None = None
    created_at: str = ""
    completed_at: str | None = None
    batch_id: str | None = None
    benchmark_id: str | None = None
    control_set_label: str | None = None
    is_primary_benchmark: bool = False
    optimization_result: JSONObject | None = None
    wdk_strategy_id: int | None = None
    wdk_step_id: int | None = None
    notes: str | None = None
    step_analysis: StepAnalysisResult | None = None
    rank_metrics: RankMetrics | None = None
    robustness: BootstrapResult | None = None
    tree_optimization: TreeOptimizationResult | None = None
