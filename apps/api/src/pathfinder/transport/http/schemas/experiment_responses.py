"""Pydantic response models for experiment types.

These models mirror the dataclasses in ``services.experiment.types`` but exist
in the transport layer so they appear in the OpenAPI schema and get
auto-generated as TypeScript types.

All field aliases use camelCase to match the existing ``to_json`` codec output.
"""

from pydantic import ConfigDict, Field, JsonValue

from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.platform.types import JSONObject
from pathfinder.services.enrichment.types import EnrichmentAnalysisType
from pathfinder.services.experiment.types.core import (
    ControlValueFormat,
    ExperimentMode,
    ExperimentStatus,
    OptimizationObjective,
    ParameterType,
    StepContributionVerdict,
)
from pathfinder.transport.http.schemas.optimization import OptimizationTrialData

_MODEL_CONFIG = ConfigDict(from_attributes=True)

# ---------------------------------------------------------------------------
# metrics.py
# ---------------------------------------------------------------------------

class ConfusionMatrixResponse(CamelModel):
    """2x2 confusion matrix counts."""

    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int

    model_config = _MODEL_CONFIG

class ExperimentMetricsResponse(CamelModel):
    """Full classification metrics derived from a confusion matrix."""

    confusion_matrix: ConfusionMatrixResponse
    sensitivity: float
    specificity: float
    precision: float
    f1_score: float
    mcc: float
    balanced_accuracy: float
    negative_predictive_value: float = Field(default=0.0)
    false_positive_rate: float = Field(default=0.0)
    false_negative_rate: float = Field(default=0.0)
    youdens_j: float = Field(default=0.0)
    total_results: int = Field(default=0)
    total_positives: int = Field(default=0)
    total_negatives: int = Field(default=0)

    model_config = _MODEL_CONFIG

class GeneInfoResponse(CamelModel):
    """Minimal gene metadata."""

    id: str
    name: str | None = None
    organism: str | None = None
    product: str | None = None

    model_config = _MODEL_CONFIG

class FoldMetricsResponse(CamelModel):
    """Metrics for a single cross-validation fold."""

    fold_index: int
    metrics: ExperimentMetricsResponse
    positive_control_ids: list[str] = Field(default_factory=list)
    negative_control_ids: list[str] = Field(default_factory=list)

    model_config = _MODEL_CONFIG

class CrossValidationResultResponse(CamelModel):
    """Aggregated cross-validation result."""

    k: int
    folds: list[FoldMetricsResponse]
    mean_metrics: ExperimentMetricsResponse
    std_metrics: dict[str, float] = Field(default_factory=dict)
    overfitting_score: float = Field(default=0.0)
    overfitting_level: str = Field(default="low")

    model_config = _MODEL_CONFIG

# ---------------------------------------------------------------------------
# enrichment.py
# ---------------------------------------------------------------------------

class EnrichmentTermResponse(CamelModel):
    """Single enriched term from WDK analysis."""

    term_id: str
    term_name: str
    gene_count: int
    background_count: int
    fold_enrichment: float
    odds_ratio: float
    p_value: float
    fdr: float
    bonferroni: float
    genes: list[str] = Field(default_factory=list)

    model_config = _MODEL_CONFIG

class EnrichmentResultResponse(CamelModel):
    """Results for a single enrichment analysis type."""

    analysis_type: EnrichmentAnalysisType
    terms: list[EnrichmentTermResponse]
    total_genes_analyzed: int = Field(default=0)
    background_size: int = Field(default=0)
    error: str | None = None

    model_config = _MODEL_CONFIG

# ---------------------------------------------------------------------------
# rank.py
# ---------------------------------------------------------------------------

class RankMetricsResponse(CamelModel):
    """Rank-based evaluation metrics computed over an ordered result list."""

    precision_at_k: dict[int, float] = Field(default_factory=dict)
    recall_at_k: dict[int, float] = Field(default_factory=dict)
    enrichment_at_k: dict[int, float] = Field(default_factory=dict)
    pr_curve: list[tuple[float, float]] = Field(default_factory=list)
    list_size_vs_recall: list[tuple[int, float]] = Field(default_factory=list)
    total_results: int = Field(default=0)

    model_config = _MODEL_CONFIG

class ConfidenceIntervalResponse(CamelModel):
    """Bootstrap confidence interval for a single metric."""

    lower: float = 0.0
    mean: float = 0.0
    upper: float = 0.0
    std: float = 0.0

    model_config = _MODEL_CONFIG

class NegativeSetVariantResponse(CamelModel):
    """Rank metrics evaluated with an alternative negative control set."""

    label: str
    rank_metrics: RankMetricsResponse
    negative_count: int = Field(default=0)

    model_config = _MODEL_CONFIG

class BootstrapResultResponse(CamelModel):
    """Robustness assessment via bootstrap resampling."""

    n_iterations: int = Field(default=0)
    metric_cis: dict[str, ConfidenceIntervalResponse] = Field(default_factory=dict)
    rank_metric_cis: dict[str, ConfidenceIntervalResponse] = Field(default_factory=dict)
    top_k_stability: float = Field(default=0.0)
    negative_set_sensitivity: list[NegativeSetVariantResponse] = Field(default_factory=list)

    model_config = _MODEL_CONFIG

# ---------------------------------------------------------------------------
# step_analysis.py
# ---------------------------------------------------------------------------

class StepEvaluationResponse(CamelModel):
    """Per-leaf-step evaluation against controls."""

    step_id: str
    search_name: str
    display_name: str
    estimated_size: int
    positive_hits: int
    positive_total: int
    negative_hits: int
    negative_total: int
    recall: float
    false_positive_rate: float
    captured_positive_ids: list[str] = Field(default_factory=list)
    captured_negative_ids: list[str] = Field(default_factory=list)
    tp_movement: int = Field(default=0)
    fp_movement: int = Field(default=0)
    fn_movement: int = Field(default=0)

    model_config = _MODEL_CONFIG

class OperatorVariantResponse(CamelModel):
    """Metrics for one boolean operator at a combine node."""

    operator: str
    positive_hits: int
    negative_hits: int
    total_results: int
    recall: float
    false_positive_rate: float
    f1_score: float

    model_config = _MODEL_CONFIG

class OperatorComparisonResponse(CamelModel):
    """Comparison of operators at a single combine node."""

    combine_node_id: str
    current_operator: str
    variants: list[OperatorVariantResponse] = Field(default_factory=list)
    recommendation: str = ""
    recommended_operator: str = Field(default="")
    precision_at_k_delta: dict[int, float] = Field(default_factory=dict)

    model_config = _MODEL_CONFIG

class StepContributionResponse(CamelModel):
    """Ablation analysis for one leaf step."""

    step_id: str
    search_name: str
    baseline_recall: float
    ablated_recall: float
    recall_delta: float
    baseline_fpr: float
    ablated_fpr: float
    fpr_delta: float
    verdict: StepContributionVerdict
    enrichment_delta: float = Field(default=0.0)
    narrative: str = ""

    model_config = _MODEL_CONFIG

class ParameterSweepPointResponse(CamelModel):
    """One data point in a parameter sensitivity sweep."""

    value: float
    positive_hits: int
    negative_hits: int
    total_results: int
    recall: float
    fpr: float
    f1: float

    model_config = _MODEL_CONFIG

class ParameterSensitivityResponse(CamelModel):
    """Sensitivity sweep for one numeric parameter on one leaf step."""

    step_id: str
    param_name: str
    current_value: float
    sweep_points: list[ParameterSweepPointResponse] = Field(default_factory=list)
    recommended_value: float = Field(default=0.0)
    recommendation: str = ""

    model_config = _MODEL_CONFIG

class StepAnalysisResultResponse(CamelModel):
    """Container for all deterministic step analysis results."""

    step_evaluations: list[StepEvaluationResponse] = Field(default_factory=list)
    operator_comparisons: list[OperatorComparisonResponse] = Field(default_factory=list)
    step_contributions: list[StepContributionResponse] = Field(default_factory=list)
    parameter_sensitivities: list[ParameterSensitivityResponse] = Field(default_factory=list)

    model_config = _MODEL_CONFIG

# ---------------------------------------------------------------------------
# optimization.py
# ---------------------------------------------------------------------------

class OptimizationSpecResponse(CamelModel):
    """Describes a single parameter to optimise."""

    name: str
    type: ParameterType
    min: float | None = None
    max: float | None = None
    step: float | None = None
    choices: list[str] | None = None

    model_config = _MODEL_CONFIG

class ThresholdKnobResponse(CamelModel):
    """A numeric parameter on a leaf step that can be tuned."""

    step_id: str
    param_name: str
    min_val: float
    max_val: float
    step_size: float | None = Field(default=None)

    model_config = _MODEL_CONFIG

class OperatorKnobResponse(CamelModel):
    """A combine-node operator that can be switched during optimization."""

    combine_node_id: str
    options: list[str] = Field(default_factory=lambda: ["INTERSECT", "UNION", "MINUS"])

    model_config = _MODEL_CONFIG

class TreeOptimizationTrialResponse(CamelModel):
    """One trial during tree-knob optimization."""

    trial_number: int
    parameters: dict[str, float | str] = Field(default_factory=dict)
    score: float = 0.0
    rank_metrics: RankMetricsResponse | None = Field(default=None)
    list_size: int = Field(default=0)

    model_config = _MODEL_CONFIG

class TreeOptimizationResultResponse(CamelModel):
    """Result of multi-step tree-knob optimization."""

    best_trial: TreeOptimizationTrialResponse | None = Field(default=None)
    all_trials: list[TreeOptimizationTrialResponse] = Field(default_factory=list)
    total_time_seconds: float = Field(default=0.0)
    objective: str = ""

    model_config = _MODEL_CONFIG

# ---------------------------------------------------------------------------
# experiment.py — ExperimentConfig and Experiment
# ---------------------------------------------------------------------------

class ExperimentConfigResponse(CamelModel):
    """Full configuration for an experiment run."""

    site_id: str
    record_type: str
    search_name: str
    parameters: JSONObject
    positive_controls: list[str]
    negative_controls: list[str]
    controls_search_name: str
    controls_param_name: str
    controls_value_format: ControlValueFormat = Field(default="newline")
    enable_cross_validation: bool = Field(default=False)
    k_folds: int = Field(default=5)
    enrichment_types: list[EnrichmentAnalysisType] = Field(default_factory=list)
    name: str = ""
    description: str = ""
    optimization_specs: list[OptimizationSpecResponse] | None = Field(default=None)
    optimization_budget: int = Field(default=30)
    optimization_objective: OptimizationObjective = Field(default="balanced_accuracy")
    parameter_display_values: dict[str, str] | None = Field(default=None)
    mode: ExperimentMode = "single"
    step_tree: JsonValue = Field(default=None)
    source_strategy_id: str | None = Field(default=None)
    optimization_target_step: str | None = Field(default=None)
    enable_step_analysis: bool = Field(default=False)
    step_analysis_phases: list[str] = Field(default_factory=list)
    control_set_id: str | None = Field(default=None)
    threshold_knobs: list[ThresholdKnobResponse] | None = Field(default=None)
    operator_knobs: list[OperatorKnobResponse] | None = Field(default=None)
    tree_optimization_objective: str = Field(default="precision_at_50")
    tree_optimization_budget: int = Field(default=50)
    max_list_size: int | None = Field(default=None)
    sort_attribute: str | None = Field(default=None)
    sort_direction: str = Field(default="ASC")
    parent_experiment_id: str | None = Field(default=None)
    target_gene_ids: list[str] | None = Field(default=None)

    model_config = _MODEL_CONFIG

class ExperimentResponse(CamelModel):
    """Full experiment with config and results."""

    id: str
    config: ExperimentConfigResponse
    user_id: str | None = Field(default=None)
    status: ExperimentStatus = "pending"
    metrics: ExperimentMetricsResponse | None = None
    cross_validation: CrossValidationResultResponse | None = Field(default=None)
    enrichment_results: list[EnrichmentResultResponse] = Field(default_factory=list)
    true_positive_genes: list[GeneInfoResponse] = Field(default_factory=list)
    false_negative_genes: list[GeneInfoResponse] = Field(default_factory=list)
    false_positive_genes: list[GeneInfoResponse] = Field(default_factory=list)
    true_negative_genes: list[GeneInfoResponse] = Field(default_factory=list)
    error: str | None = None
    total_time_seconds: float | None = Field(default=None)
    created_at: str = Field(default="")
    completed_at: str | None = Field(default=None)
    batch_id: str | None = Field(default=None)
    benchmark_id: str | None = Field(default=None)
    control_set_label: str | None = Field(default=None)
    is_primary_benchmark: bool = Field(default=False)
    optimization_result: JSONObject | None = Field(default=None)
    wdk_strategy_id: int | None = Field(default=None)
    wdk_step_id: int | None = Field(default=None)
    notes: str | None = None
    step_analysis: StepAnalysisResultResponse | None = Field(default=None)
    rank_metrics: RankMetricsResponse | None = Field(default=None)
    robustness: BootstrapResultResponse | None = None
    tree_optimization: TreeOptimizationResultResponse | None = Field(default=None)

    model_config = _MODEL_CONFIG

class ExperimentSummaryResponse(CamelModel):
    """Lightweight experiment summary for list views."""

    id: str
    name: str
    site_id: str
    search_name: str
    record_type: str
    mode: ExperimentMode
    status: ExperimentStatus
    f1_score: float | None = Field(default=None)
    sensitivity: float | None = None
    specificity: float | None = None
    total_positives: int
    total_negatives: int
    created_at: str
    batch_id: str | None = Field(default=None)
    benchmark_id: str | None = Field(default=None)
    control_set_label: str | None = Field(default=None)
    is_primary_benchmark: bool = Field(default=False)

    model_config = _MODEL_CONFIG

# ---------------------------------------------------------------------------
# Progress data models
# ---------------------------------------------------------------------------

class TrialProgressDataResponse(CamelModel):
    """Progress data for a single optimization trial."""

    trial_number: int
    total_trials: int
    status: str
    score: float | None = None
    recall: float | None = None
    false_positive_rate: float | None = Field(default=None)
    estimated_size: int | None = Field(default=None)
    parameters: dict[str, JsonValue] | None = None

    model_config = _MODEL_CONFIG

class StepAnalysisProgressDataResponse(CamelModel):
    """Progress data for step analysis."""

    phase: str
    current_step: int | None = Field(default=None)
    total_steps: int | None = Field(default=None)
    step_id: str | None = Field(default=None)
    search_name: str | None = Field(default=None)
    message: str | None = None

    model_config = _MODEL_CONFIG

class ExperimentProgressDataResponse(CamelModel):
    """Progress data for experiment execution."""

    phase: str
    message: str | None = None
    trial_progress: TrialProgressDataResponse | None = Field(default=None)
    step_analysis_progress: StepAnalysisProgressDataResponse | None = Field(default=None)

    model_config = _MODEL_CONFIG

class OptimizationResultResponse(CamelModel):
    """Complete optimization result."""

    optimization_id: str
    status: str
    best_trial: OptimizationTrialData | None = Field(default=None)
    all_trials: list[OptimizationTrialData] = Field(default_factory=list)
    pareto_frontier: list[OptimizationTrialData] = Field(default_factory=list)
    sensitivity: dict[str, float] = Field(default_factory=dict)
    total_time_seconds: float = Field(default=0)
    total_trials: int = Field(default=0)

    model_config = _MODEL_CONFIG

# ---------------------------------------------------------------------------
# Control set summary
# ---------------------------------------------------------------------------

class ControlSetSummaryResponse(CamelModel):
    """Control set summary for listing."""

    id: str
    name: str
    source: str
    organism: str | None = None
    positive_count: int
    negative_count: int

    model_config = _MODEL_CONFIG
