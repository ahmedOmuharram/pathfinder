"""Pydantic response models for experiment types.

These models mirror the dataclasses in ``services.experiment.types`` but exist
in the transport layer so they appear in the OpenAPI schema and get
auto-generated as TypeScript types.

All field aliases use camelCase to match the existing ``to_json`` codec output.
"""

from pydantic import BaseModel, ConfigDict, Field

from veupath_chatbot.platform.types import JSONObject, JSONValue
from veupath_chatbot.services.experiment.types.core import (
    ControlValueFormat,
    EnrichmentAnalysisType,
    ExperimentMode,
    ExperimentStatus,
    OptimizationObjective,
    ParameterType,
    StepContributionVerdict,
)
from veupath_chatbot.transport.http.schemas.optimization import OptimizationTrialData

_MODEL_CONFIG = ConfigDict(populate_by_name=True, from_attributes=True)


# ---------------------------------------------------------------------------
# metrics.py
# ---------------------------------------------------------------------------


class ConfusionMatrixResponse(BaseModel):
    """2x2 confusion matrix counts."""

    true_positives: int = Field(alias="truePositives")
    false_positives: int = Field(alias="falsePositives")
    true_negatives: int = Field(alias="trueNegatives")
    false_negatives: int = Field(alias="falseNegatives")

    model_config = _MODEL_CONFIG


class ExperimentMetricsResponse(BaseModel):
    """Full classification metrics derived from a confusion matrix."""

    confusion_matrix: ConfusionMatrixResponse = Field(alias="confusionMatrix")
    sensitivity: float
    specificity: float
    precision: float
    f1_score: float = Field(alias="f1Score")
    mcc: float
    balanced_accuracy: float = Field(alias="balancedAccuracy")
    negative_predictive_value: float = Field(
        default=0.0, alias="negativePredictiveValue"
    )
    false_positive_rate: float = Field(default=0.0, alias="falsePositiveRate")
    false_negative_rate: float = Field(default=0.0, alias="falseNegativeRate")
    youdens_j: float = Field(default=0.0, alias="youdensJ")
    total_results: int = Field(default=0, alias="totalResults")
    total_positives: int = Field(default=0, alias="totalPositives")
    total_negatives: int = Field(default=0, alias="totalNegatives")

    model_config = _MODEL_CONFIG


class GeneInfoResponse(BaseModel):
    """Minimal gene metadata."""

    id: str
    name: str | None = None
    organism: str | None = None
    product: str | None = None

    model_config = _MODEL_CONFIG


class FoldMetricsResponse(BaseModel):
    """Metrics for a single cross-validation fold."""

    fold_index: int = Field(alias="foldIndex")
    metrics: ExperimentMetricsResponse
    positive_control_ids: list[str] = Field(
        default_factory=list, alias="positiveControlIds"
    )
    negative_control_ids: list[str] = Field(
        default_factory=list, alias="negativeControlIds"
    )

    model_config = _MODEL_CONFIG


class CrossValidationResultResponse(BaseModel):
    """Aggregated cross-validation result."""

    k: int
    folds: list[FoldMetricsResponse]
    mean_metrics: ExperimentMetricsResponse = Field(alias="meanMetrics")
    std_metrics: dict[str, float] = Field(default_factory=dict, alias="stdMetrics")
    overfitting_score: float = Field(default=0.0, alias="overfittingScore")
    overfitting_level: str = Field(default="low", alias="overfittingLevel")

    model_config = _MODEL_CONFIG


# ---------------------------------------------------------------------------
# enrichment.py
# ---------------------------------------------------------------------------


class EnrichmentTermResponse(BaseModel):
    """Single enriched term from WDK analysis."""

    term_id: str = Field(alias="termId")
    term_name: str = Field(alias="termName")
    gene_count: int = Field(alias="geneCount")
    background_count: int = Field(alias="backgroundCount")
    fold_enrichment: float = Field(alias="foldEnrichment")
    odds_ratio: float = Field(alias="oddsRatio")
    p_value: float = Field(alias="pValue")
    fdr: float
    bonferroni: float
    genes: list[str] = Field(default_factory=list)

    model_config = _MODEL_CONFIG


class EnrichmentResultResponse(BaseModel):
    """Results for a single enrichment analysis type."""

    analysis_type: EnrichmentAnalysisType = Field(alias="analysisType")
    terms: list[EnrichmentTermResponse]
    total_genes_analyzed: int = Field(default=0, alias="totalGenesAnalyzed")
    background_size: int = Field(default=0, alias="backgroundSize")
    error: str | None = None

    model_config = _MODEL_CONFIG


# ---------------------------------------------------------------------------
# rank.py
# ---------------------------------------------------------------------------


class RankMetricsResponse(BaseModel):
    """Rank-based evaluation metrics computed over an ordered result list."""

    precision_at_k: dict[int, float] = Field(default_factory=dict, alias="precisionAtK")
    recall_at_k: dict[int, float] = Field(default_factory=dict, alias="recallAtK")
    enrichment_at_k: dict[int, float] = Field(
        default_factory=dict, alias="enrichmentAtK"
    )
    pr_curve: list[tuple[float, float]] = Field(default_factory=list, alias="prCurve")
    list_size_vs_recall: list[tuple[int, float]] = Field(
        default_factory=list, alias="listSizeVsRecall"
    )
    total_results: int = Field(default=0, alias="totalResults")

    model_config = _MODEL_CONFIG


class ConfidenceIntervalResponse(BaseModel):
    """Bootstrap confidence interval for a single metric."""

    lower: float = 0.0
    mean: float = 0.0
    upper: float = 0.0
    std: float = 0.0

    model_config = _MODEL_CONFIG


class NegativeSetVariantResponse(BaseModel):
    """Rank metrics evaluated with an alternative negative control set."""

    label: str
    rank_metrics: RankMetricsResponse = Field(alias="rankMetrics")
    negative_count: int = Field(default=0, alias="negativeCount")

    model_config = _MODEL_CONFIG


class BootstrapResultResponse(BaseModel):
    """Robustness assessment via bootstrap resampling."""

    n_iterations: int = Field(default=0, alias="nIterations")
    metric_cis: dict[str, ConfidenceIntervalResponse] = Field(
        default_factory=dict, alias="metricCis"
    )
    rank_metric_cis: dict[str, ConfidenceIntervalResponse] = Field(
        default_factory=dict, alias="rankMetricCis"
    )
    top_k_stability: float = Field(default=0.0, alias="topKStability")
    negative_set_sensitivity: list[NegativeSetVariantResponse] = Field(
        default_factory=list, alias="negativeSetSensitivity"
    )

    model_config = _MODEL_CONFIG


# ---------------------------------------------------------------------------
# step_analysis.py
# ---------------------------------------------------------------------------


class StepEvaluationResponse(BaseModel):
    """Per-leaf-step evaluation against controls."""

    step_id: str = Field(alias="stepId")
    search_name: str = Field(alias="searchName")
    display_name: str = Field(alias="displayName")
    result_count: int = Field(alias="resultCount")
    positive_hits: int = Field(alias="positiveHits")
    positive_total: int = Field(alias="positiveTotal")
    negative_hits: int = Field(alias="negativeHits")
    negative_total: int = Field(alias="negativeTotal")
    recall: float
    false_positive_rate: float = Field(alias="falsePositiveRate")
    captured_positive_ids: list[str] = Field(
        default_factory=list, alias="capturedPositiveIds"
    )
    captured_negative_ids: list[str] = Field(
        default_factory=list, alias="capturedNegativeIds"
    )
    tp_movement: int = Field(default=0, alias="tpMovement")
    fp_movement: int = Field(default=0, alias="fpMovement")
    fn_movement: int = Field(default=0, alias="fnMovement")

    model_config = _MODEL_CONFIG


class OperatorVariantResponse(BaseModel):
    """Metrics for one boolean operator at a combine node."""

    operator: str
    positive_hits: int = Field(alias="positiveHits")
    negative_hits: int = Field(alias="negativeHits")
    total_results: int = Field(alias="totalResults")
    recall: float
    false_positive_rate: float = Field(alias="falsePositiveRate")
    f1_score: float = Field(alias="f1Score")

    model_config = _MODEL_CONFIG


class OperatorComparisonResponse(BaseModel):
    """Comparison of operators at a single combine node."""

    combine_node_id: str = Field(alias="combineNodeId")
    current_operator: str = Field(alias="currentOperator")
    variants: list[OperatorVariantResponse] = Field(default_factory=list)
    recommendation: str = ""
    recommended_operator: str = Field(default="", alias="recommendedOperator")
    precision_at_k_delta: dict[int, float] = Field(
        default_factory=dict, alias="precisionAtKDelta"
    )

    model_config = _MODEL_CONFIG


class StepContributionResponse(BaseModel):
    """Ablation analysis for one leaf step."""

    step_id: str = Field(alias="stepId")
    search_name: str = Field(alias="searchName")
    baseline_recall: float = Field(alias="baselineRecall")
    ablated_recall: float = Field(alias="ablatedRecall")
    recall_delta: float = Field(alias="recallDelta")
    baseline_fpr: float = Field(alias="baselineFpr")
    ablated_fpr: float = Field(alias="ablatedFpr")
    fpr_delta: float = Field(alias="fprDelta")
    verdict: StepContributionVerdict
    enrichment_delta: float = Field(default=0.0, alias="enrichmentDelta")
    narrative: str = ""

    model_config = _MODEL_CONFIG


class ParameterSweepPointResponse(BaseModel):
    """One data point in a parameter sensitivity sweep."""

    value: float
    positive_hits: int = Field(alias="positiveHits")
    negative_hits: int = Field(alias="negativeHits")
    total_results: int = Field(alias="totalResults")
    recall: float
    fpr: float
    f1: float

    model_config = _MODEL_CONFIG


class ParameterSensitivityResponse(BaseModel):
    """Sensitivity sweep for one numeric parameter on one leaf step."""

    step_id: str = Field(alias="stepId")
    param_name: str = Field(alias="paramName")
    current_value: float = Field(alias="currentValue")
    sweep_points: list[ParameterSweepPointResponse] = Field(
        default_factory=list, alias="sweepPoints"
    )
    recommended_value: float = Field(default=0.0, alias="recommendedValue")
    recommendation: str = ""

    model_config = _MODEL_CONFIG


class StepAnalysisResultResponse(BaseModel):
    """Container for all deterministic step analysis results."""

    step_evaluations: list[StepEvaluationResponse] = Field(
        default_factory=list, alias="stepEvaluations"
    )
    operator_comparisons: list[OperatorComparisonResponse] = Field(
        default_factory=list, alias="operatorComparisons"
    )
    step_contributions: list[StepContributionResponse] = Field(
        default_factory=list, alias="stepContributions"
    )
    parameter_sensitivities: list[ParameterSensitivityResponse] = Field(
        default_factory=list, alias="parameterSensitivities"
    )

    model_config = _MODEL_CONFIG


# ---------------------------------------------------------------------------
# optimization.py
# ---------------------------------------------------------------------------


class OptimizationSpecResponse(BaseModel):
    """Describes a single parameter to optimise."""

    name: str
    type: ParameterType
    min: float | None = None
    max: float | None = None
    step: float | None = None
    choices: list[str] | None = None

    model_config = _MODEL_CONFIG


class ThresholdKnobResponse(BaseModel):
    """A numeric parameter on a leaf step that can be tuned."""

    step_id: str = Field(alias="stepId")
    param_name: str = Field(alias="paramName")
    min_val: float = Field(alias="minVal")
    max_val: float = Field(alias="maxVal")
    step_size: float | None = Field(default=None, alias="stepSize")

    model_config = _MODEL_CONFIG


class OperatorKnobResponse(BaseModel):
    """A combine-node operator that can be switched during optimization."""

    combine_node_id: str = Field(alias="combineNodeId")
    options: list[str] = Field(default_factory=lambda: ["INTERSECT", "UNION", "MINUS"])

    model_config = _MODEL_CONFIG


class TreeOptimizationTrialResponse(BaseModel):
    """One trial during tree-knob optimization."""

    trial_number: int = Field(alias="trialNumber")
    parameters: dict[str, float | str] = Field(default_factory=dict)
    score: float = 0.0
    rank_metrics: RankMetricsResponse | None = Field(default=None, alias="rankMetrics")
    list_size: int = Field(default=0, alias="listSize")

    model_config = _MODEL_CONFIG


class TreeOptimizationResultResponse(BaseModel):
    """Result of multi-step tree-knob optimization."""

    best_trial: TreeOptimizationTrialResponse | None = Field(
        default=None, alias="bestTrial"
    )
    all_trials: list[TreeOptimizationTrialResponse] = Field(
        default_factory=list, alias="allTrials"
    )
    total_time_seconds: float = Field(default=0.0, alias="totalTimeSeconds")
    objective: str = ""

    model_config = _MODEL_CONFIG


# ---------------------------------------------------------------------------
# experiment.py — ExperimentConfig and Experiment
# ---------------------------------------------------------------------------


class ExperimentConfigResponse(BaseModel):
    """Full configuration for an experiment run."""

    site_id: str = Field(alias="siteId")
    record_type: str = Field(alias="recordType")
    search_name: str = Field(alias="searchName")
    parameters: JSONObject
    positive_controls: list[str] = Field(alias="positiveControls")
    negative_controls: list[str] = Field(alias="negativeControls")
    controls_search_name: str = Field(alias="controlsSearchName")
    controls_param_name: str = Field(alias="controlsParamName")
    controls_value_format: ControlValueFormat = Field(
        default="newline", alias="controlsValueFormat"
    )
    enable_cross_validation: bool = Field(default=False, alias="enableCrossValidation")
    k_folds: int = Field(default=5, alias="kFolds")
    enrichment_types: list[EnrichmentAnalysisType] = Field(
        default_factory=list, alias="enrichmentTypes"
    )
    name: str = ""
    description: str = ""
    optimization_specs: list[OptimizationSpecResponse] | None = Field(
        default=None, alias="optimizationSpecs"
    )
    optimization_budget: int = Field(default=30, alias="optimizationBudget")
    optimization_objective: OptimizationObjective = Field(
        default="balanced_accuracy", alias="optimizationObjective"
    )
    parameter_display_values: dict[str, str] | None = Field(
        default=None, alias="parameterDisplayValues"
    )
    mode: ExperimentMode = "single"
    step_tree: JSONValue = Field(default=None, alias="stepTree")
    source_strategy_id: str | None = Field(default=None, alias="sourceStrategyId")
    optimization_target_step: str | None = Field(
        default=None, alias="optimizationTargetStep"
    )
    enable_step_analysis: bool = Field(default=False, alias="enableStepAnalysis")
    step_analysis_phases: list[str] = Field(
        default_factory=list, alias="stepAnalysisPhases"
    )
    control_set_id: str | None = Field(default=None, alias="controlSetId")
    threshold_knobs: list[ThresholdKnobResponse] | None = Field(
        default=None, alias="thresholdKnobs"
    )
    operator_knobs: list[OperatorKnobResponse] | None = Field(
        default=None, alias="operatorKnobs"
    )
    tree_optimization_objective: str = Field(
        default="precision_at_50", alias="treeOptimizationObjective"
    )
    tree_optimization_budget: int = Field(default=50, alias="treeOptimizationBudget")
    max_list_size: int | None = Field(default=None, alias="maxListSize")
    sort_attribute: str | None = Field(default=None, alias="sortAttribute")
    sort_direction: str = Field(default="ASC", alias="sortDirection")
    parent_experiment_id: str | None = Field(default=None, alias="parentExperimentId")
    target_gene_ids: list[str] | None = Field(default=None, alias="targetGeneIds")

    model_config = _MODEL_CONFIG


class ExperimentResponse(BaseModel):
    """Full experiment with config and results."""

    id: str
    config: ExperimentConfigResponse
    user_id: str | None = Field(default=None, alias="userId")
    status: ExperimentStatus = "pending"
    metrics: ExperimentMetricsResponse | None = None
    cross_validation: CrossValidationResultResponse | None = Field(
        default=None, alias="crossValidation"
    )
    enrichment_results: list[EnrichmentResultResponse] = Field(
        default_factory=list, alias="enrichmentResults"
    )
    true_positive_genes: list[GeneInfoResponse] = Field(
        default_factory=list, alias="truePositiveGenes"
    )
    false_negative_genes: list[GeneInfoResponse] = Field(
        default_factory=list, alias="falseNegativeGenes"
    )
    false_positive_genes: list[GeneInfoResponse] = Field(
        default_factory=list, alias="falsePositiveGenes"
    )
    true_negative_genes: list[GeneInfoResponse] = Field(
        default_factory=list, alias="trueNegativeGenes"
    )
    error: str | None = None
    total_time_seconds: float | None = Field(default=None, alias="totalTimeSeconds")
    created_at: str = Field(default="", alias="createdAt")
    completed_at: str | None = Field(default=None, alias="completedAt")
    batch_id: str | None = Field(default=None, alias="batchId")
    benchmark_id: str | None = Field(default=None, alias="benchmarkId")
    control_set_label: str | None = Field(default=None, alias="controlSetLabel")
    is_primary_benchmark: bool = Field(default=False, alias="isPrimaryBenchmark")
    optimization_result: JSONObject | None = Field(
        default=None, alias="optimizationResult"
    )
    wdk_strategy_id: int | None = Field(default=None, alias="wdkStrategyId")
    wdk_step_id: int | None = Field(default=None, alias="wdkStepId")
    notes: str | None = None
    step_analysis: StepAnalysisResultResponse | None = Field(
        default=None, alias="stepAnalysis"
    )
    rank_metrics: RankMetricsResponse | None = Field(default=None, alias="rankMetrics")
    robustness: BootstrapResultResponse | None = None
    tree_optimization: TreeOptimizationResultResponse | None = Field(
        default=None, alias="treeOptimization"
    )

    model_config = _MODEL_CONFIG


class ExperimentSummaryResponse(BaseModel):
    """Lightweight experiment summary for list views."""

    id: str
    name: str
    site_id: str = Field(alias="siteId")
    search_name: str = Field(alias="searchName")
    record_type: str = Field(alias="recordType")
    mode: ExperimentMode
    status: ExperimentStatus
    f1_score: float | None = Field(default=None, alias="f1Score")
    sensitivity: float | None = None
    specificity: float | None = None
    total_positives: int = Field(alias="totalPositives")
    total_negatives: int = Field(alias="totalNegatives")
    created_at: str = Field(alias="createdAt")
    batch_id: str | None = Field(default=None, alias="batchId")
    benchmark_id: str | None = Field(default=None, alias="benchmarkId")
    control_set_label: str | None = Field(default=None, alias="controlSetLabel")
    is_primary_benchmark: bool = Field(default=False, alias="isPrimaryBenchmark")

    model_config = _MODEL_CONFIG


# ---------------------------------------------------------------------------
# Progress data models
# ---------------------------------------------------------------------------


class TrialProgressDataResponse(BaseModel):
    """Progress data for a single optimization trial."""

    trial_number: int = Field(alias="trialNumber")
    total_trials: int = Field(alias="totalTrials")
    status: str
    score: float | None = None
    recall: float | None = None
    false_positive_rate: float | None = Field(default=None, alias="falsePositiveRate")
    result_count: int | None = Field(default=None, alias="resultCount")
    parameters: dict[str, JSONValue] | None = None

    model_config = _MODEL_CONFIG


class StepAnalysisProgressDataResponse(BaseModel):
    """Progress data for step analysis."""

    phase: str
    current_step: int | None = Field(default=None, alias="currentStep")
    total_steps: int | None = Field(default=None, alias="totalSteps")
    step_id: str | None = Field(default=None, alias="stepId")
    search_name: str | None = Field(default=None, alias="searchName")
    message: str | None = None

    model_config = _MODEL_CONFIG


class ExperimentProgressDataResponse(BaseModel):
    """Progress data for experiment execution."""

    phase: str
    message: str | None = None
    trial_progress: TrialProgressDataResponse | None = Field(
        default=None, alias="trialProgress"
    )
    step_analysis_progress: StepAnalysisProgressDataResponse | None = Field(
        default=None, alias="stepAnalysisProgress"
    )

    model_config = _MODEL_CONFIG


class OptimizationResultResponse(BaseModel):
    """Complete optimization result."""

    optimization_id: str = Field(alias="optimizationId")
    status: str
    best_trial: OptimizationTrialData | None = Field(default=None, alias="bestTrial")
    all_trials: list[OptimizationTrialData] = Field(
        default_factory=list, alias="allTrials"
    )
    pareto_frontier: list[OptimizationTrialData] = Field(
        default_factory=list, alias="paretoFrontier"
    )
    sensitivity: dict[str, float] = Field(default_factory=dict)
    total_time_seconds: float = Field(default=0, alias="totalTimeSeconds")
    total_trials: int = Field(default=0, alias="totalTrials")

    model_config = _MODEL_CONFIG


# ---------------------------------------------------------------------------
# Control set summary
# ---------------------------------------------------------------------------


class ControlSetSummaryResponse(BaseModel):
    """Control set summary for listing."""

    id: str
    name: str
    source: str
    organism: str | None = None
    positive_count: int = Field(alias="positiveCount")
    negative_count: int = Field(alias="negativeCount")

    model_config = _MODEL_CONFIG
