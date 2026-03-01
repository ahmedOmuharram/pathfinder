"""Shared data types for the Experiment Lab."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, cast

from veupath_chatbot.platform.types import JSONObject, JSONValue

EnrichmentAnalysisType = Literal[
    "go_function", "go_component", "go_process", "pathway", "word"
]

ExperimentMode = Literal["single", "multi-step", "import"]

ParameterType = Literal["numeric", "integer", "categorical"]

ExperimentStatus = Literal["pending", "running", "completed", "error", "cancelled"]

ExperimentProgressPhase = Literal[
    "started",
    "evaluating",
    "optimizing",
    "cross_validating",
    "enriching",
    "step_analysis",
    "completed",
    "error",
]

ControlValueFormat = Literal["newline", "json_list", "comma"]

WizardStep = Literal["search", "parameters", "controls", "run", "results", "analysis"]

OptimizationObjective = Literal[
    "f1",
    "f_beta",
    "recall",
    "precision",
    "specificity",
    "balanced_accuracy",
    "mcc",
    "youdens_j",
    "custom",
]


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


@dataclass(frozen=True, slots=True)
class EnrichmentTerm:
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
    genes: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class EnrichmentResult:
    """Results for a single enrichment analysis type."""

    analysis_type: EnrichmentAnalysisType
    terms: list[EnrichmentTerm]
    total_genes_analyzed: int
    background_size: int


@dataclass(slots=True)
class OptimizationSpec:
    """Describes a single parameter to optimise."""

    name: str
    type: ParameterType
    min: float | None = None
    max: float | None = None
    step: float | None = None
    choices: list[str] | None = None


# ---------------------------------------------------------------------------
# Rank-based evaluation types
# ---------------------------------------------------------------------------

DEFAULT_K_VALUES: list[int] = [10, 25, 50, 100]

ControlSetSource = Literal["paper", "curation", "db_build", "other"]


@dataclass(frozen=True, slots=True)
class ControlSetSummary:
    """Lightweight control set reference for experiment configs."""

    id: str
    name: str
    source: ControlSetSource
    tags: list[str] = field(default_factory=list)
    positive_count: int = 0
    negative_count: int = 0


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


# ---------------------------------------------------------------------------
# Tree optimization knob types
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ThresholdKnob:
    """A numeric parameter on a leaf step that can be tuned."""

    step_id: str
    param_name: str
    min_val: float
    max_val: float
    step_size: float | None = None


@dataclass(frozen=True, slots=True)
class OperatorKnob:
    """A combine-node operator that can be switched during optimization."""

    combine_node_id: str
    options: list[str] = field(default_factory=lambda: ["INTERSECT", "UNION", "MINUS"])


@dataclass(frozen=True, slots=True)
class TreeOptimizationTrial:
    """One trial during tree-knob optimization."""

    trial_number: int
    parameters: dict[str, float | str]
    score: float
    rank_metrics: RankMetrics | None = None
    list_size: int = 0


@dataclass(frozen=True, slots=True)
class TreeOptimizationResult:
    """Result of multi-step tree-knob optimization."""

    best_trial: TreeOptimizationTrial | None = None
    all_trials: list[TreeOptimizationTrial] = field(default_factory=list)
    total_time_seconds: float = 0.0
    objective: str = ""


# ---------------------------------------------------------------------------
# Step Analysis types (deterministic decomposition)
# ---------------------------------------------------------------------------

StepContributionVerdict = Literal["essential", "helpful", "neutral", "harmful"]


@dataclass(frozen=True, slots=True)
class StepEvaluation:
    """Per-leaf-step evaluation against controls."""

    step_id: str
    search_name: str
    display_name: str
    result_count: int
    positive_hits: int
    positive_total: int
    negative_hits: int
    negative_total: int
    recall: float
    false_positive_rate: float
    captured_positive_ids: list[str] = field(default_factory=list)
    captured_negative_ids: list[str] = field(default_factory=list)
    tp_movement: int = 0
    fp_movement: int = 0
    fn_movement: int = 0


@dataclass(frozen=True, slots=True)
class OperatorVariant:
    """Metrics for one boolean operator at a combine node."""

    operator: str
    positive_hits: int
    negative_hits: int
    total_results: int
    recall: float
    false_positive_rate: float
    f1_score: float


@dataclass(frozen=True, slots=True)
class OperatorComparison:
    """Comparison of operators at a single combine node."""

    combine_node_id: str
    current_operator: str
    variants: list[OperatorVariant] = field(default_factory=list)
    recommendation: str = ""
    recommended_operator: str = ""
    precision_at_k_delta: dict[int, float] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class StepContribution:
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
    enrichment_delta: float = 0.0
    narrative: str = ""


@dataclass(frozen=True, slots=True)
class ParameterSweepPoint:
    """One data point in a parameter sensitivity sweep."""

    value: float
    positive_hits: int
    negative_hits: int
    total_results: int
    recall: float
    fpr: float
    f1: float


@dataclass(frozen=True, slots=True)
class ParameterSensitivity:
    """Sensitivity sweep for one numeric parameter on one leaf step."""

    step_id: str
    param_name: str
    current_value: float
    sweep_points: list[ParameterSweepPoint] = field(default_factory=list)
    recommended_value: float = 0.0
    recommendation: str = ""


@dataclass(frozen=True, slots=True)
class StepAnalysisResult:
    """Container for all deterministic step analysis results."""

    step_evaluations: list[StepEvaluation] = field(default_factory=list)
    operator_comparisons: list[OperatorComparison] = field(default_factory=list)
    step_contributions: list[StepContribution] = field(default_factory=list)
    parameter_sensitivities: list[ParameterSensitivity] = field(default_factory=list)


@dataclass(slots=True)
class ExperimentConfig:
    """Full configuration for an experiment run.

    Supports three modes:

    * **single** (default): one search + parameters (backward compatible).
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


def metrics_to_json(m: ExperimentMetrics) -> JSONObject:
    """Serialize :class:`ExperimentMetrics` to a JSON-compatible dict."""
    return {
        "confusionMatrix": {
            "truePositives": m.confusion_matrix.true_positives,
            "falsePositives": m.confusion_matrix.false_positives,
            "trueNegatives": m.confusion_matrix.true_negatives,
            "falseNegatives": m.confusion_matrix.false_negatives,
        },
        "sensitivity": round(m.sensitivity, 4),
        "specificity": round(m.specificity, 4),
        "precision": round(m.precision, 4),
        "negativePredictiveValue": round(m.negative_predictive_value, 4),
        "falsePositiveRate": round(m.false_positive_rate, 4),
        "falseNegativeRate": round(m.false_negative_rate, 4),
        "f1Score": round(m.f1_score, 4),
        "mcc": round(m.mcc, 4),
        "balancedAccuracy": round(m.balanced_accuracy, 4),
        "youdensJ": round(m.youdens_j, 4),
        "totalResults": m.total_results,
        "totalPositives": m.total_positives,
        "totalNegatives": m.total_negatives,
    }


def gene_info_to_json(g: GeneInfo) -> JSONObject:
    """Serialize :class:`GeneInfo` to a JSON-compatible dict."""
    return {
        "id": g.id,
        "name": g.name,
        "organism": g.organism,
        "product": g.product,
    }


def fold_metrics_to_json(fm: FoldMetrics) -> JSONObject:
    """Serialize :class:`FoldMetrics` to a JSON-compatible dict."""
    return {
        "foldIndex": fm.fold_index,
        "metrics": metrics_to_json(fm.metrics),
        "positiveControlIds": list(fm.positive_control_ids),
        "negativeControlIds": list(fm.negative_control_ids),
    }


def cv_result_to_json(cv: CrossValidationResult) -> JSONObject:
    """Serialize :class:`CrossValidationResult` to a JSON-compatible dict."""
    return {
        "k": cv.k,
        "folds": [fold_metrics_to_json(f) for f in cv.folds],
        "meanMetrics": metrics_to_json(cv.mean_metrics),
        "stdMetrics": {k: round(v, 4) for k, v in cv.std_metrics.items()},
        "overfittingScore": round(cv.overfitting_score, 4),
        "overfittingLevel": cv.overfitting_level,
    }


def enrichment_term_to_json(t: EnrichmentTerm) -> JSONObject:
    """Serialize :class:`EnrichmentTerm` to a JSON-compatible dict."""
    return {
        "termId": t.term_id,
        "termName": t.term_name,
        "geneCount": t.gene_count,
        "backgroundCount": t.background_count,
        "foldEnrichment": round(t.fold_enrichment, 4),
        "oddsRatio": round(t.odds_ratio, 4),
        "pValue": t.p_value,
        "fdr": t.fdr,
        "bonferroni": t.bonferroni,
        "genes": list(t.genes),
    }


def enrichment_result_to_json(er: EnrichmentResult) -> JSONObject:
    """Serialize :class:`EnrichmentResult` to a JSON-compatible dict."""
    return {
        "analysisType": er.analysis_type,
        "terms": [enrichment_term_to_json(t) for t in er.terms],
        "totalGenesAnalyzed": er.total_genes_analyzed,
        "backgroundSize": er.background_size,
    }


def rank_metrics_to_json(rm: RankMetrics) -> JSONObject:
    """Serialize :class:`RankMetrics` to a JSON-compatible dict."""
    return {
        "precisionAtK": {str(k): round(v, 4) for k, v in rm.precision_at_k.items()},
        "recallAtK": {str(k): round(v, 4) for k, v in rm.recall_at_k.items()},
        "enrichmentAtK": {str(k): round(v, 4) for k, v in rm.enrichment_at_k.items()},
        "prCurve": [[round(p, 4), round(r, 4)] for p, r in rm.pr_curve],
        "listSizeVsRecall": [[s, round(r, 4)] for s, r in rm.list_size_vs_recall],
        "totalResults": rm.total_results,
    }


def confidence_interval_to_json(ci: ConfidenceInterval) -> JSONObject:
    """Serialize :class:`ConfidenceInterval` to a JSON-compatible dict."""
    return {
        "lower": round(ci.lower, 4),
        "mean": round(ci.mean, 4),
        "upper": round(ci.upper, 4),
        "std": round(ci.std, 4),
    }


def negative_set_variant_to_json(v: NegativeSetVariant) -> JSONObject:
    """Serialize :class:`NegativeSetVariant` to a JSON-compatible dict."""
    return {
        "label": v.label,
        "negativeCount": v.negative_count,
        "rankMetrics": rank_metrics_to_json(v.rank_metrics),
    }


def bootstrap_result_to_json(br: BootstrapResult) -> JSONObject:
    """Serialize :class:`BootstrapResult` to a JSON-compatible dict."""
    return {
        "nIterations": br.n_iterations,
        "metricCis": {
            k: confidence_interval_to_json(v) for k, v in br.metric_cis.items()
        },
        "rankMetricCis": {
            k: confidence_interval_to_json(v) for k, v in br.rank_metric_cis.items()
        },
        "topKStability": round(br.top_k_stability, 4),
        "negativeSetSensitivity": [
            negative_set_variant_to_json(v) for v in br.negative_set_sensitivity
        ],
    }


def tree_optimization_trial_to_json(t: TreeOptimizationTrial) -> JSONObject:
    """Serialize :class:`TreeOptimizationTrial` to a JSON-compatible dict."""
    return {
        "trialNumber": t.trial_number,
        "parameters": dict(t.parameters.items()),
        "score": round(t.score, 4),
        "rankMetrics": rank_metrics_to_json(t.rank_metrics) if t.rank_metrics else None,
        "listSize": t.list_size,
    }


def tree_optimization_result_to_json(r: TreeOptimizationResult) -> JSONObject:
    """Serialize :class:`TreeOptimizationResult` to a JSON-compatible dict."""
    return {
        "bestTrial": tree_optimization_trial_to_json(r.best_trial)
        if r.best_trial
        else None,
        "allTrials": [tree_optimization_trial_to_json(t) for t in r.all_trials],
        "totalTimeSeconds": round(r.total_time_seconds, 2),
        "objective": r.objective,
    }


def step_evaluation_to_json(se: StepEvaluation) -> JSONObject:
    """Serialize :class:`StepEvaluation` to a JSON-compatible dict."""
    return {
        "stepId": se.step_id,
        "searchName": se.search_name,
        "displayName": se.display_name,
        "resultCount": se.result_count,
        "positiveHits": se.positive_hits,
        "positiveTotal": se.positive_total,
        "negativeHits": se.negative_hits,
        "negativeTotal": se.negative_total,
        "recall": round(se.recall, 4),
        "falsePositiveRate": round(se.false_positive_rate, 4),
        "capturedPositiveIds": list(se.captured_positive_ids),
        "capturedNegativeIds": list(se.captured_negative_ids),
        "tpMovement": se.tp_movement,
        "fpMovement": se.fp_movement,
        "fnMovement": se.fn_movement,
    }


def operator_variant_to_json(ov: OperatorVariant) -> JSONObject:
    """Serialize :class:`OperatorVariant` to a JSON-compatible dict."""
    return {
        "operator": ov.operator,
        "positiveHits": ov.positive_hits,
        "negativeHits": ov.negative_hits,
        "totalResults": ov.total_results,
        "recall": round(ov.recall, 4),
        "falsePositiveRate": round(ov.false_positive_rate, 4),
        "f1Score": round(ov.f1_score, 4),
    }


def operator_comparison_to_json(oc: OperatorComparison) -> JSONObject:
    """Serialize :class:`OperatorComparison` to a JSON-compatible dict."""
    return {
        "combineNodeId": oc.combine_node_id,
        "currentOperator": oc.current_operator,
        "variants": [operator_variant_to_json(v) for v in oc.variants],
        "recommendation": oc.recommendation,
        "recommendedOperator": oc.recommended_operator,
        "precisionAtKDelta": {
            str(k): round(v, 4) for k, v in oc.precision_at_k_delta.items()
        },
    }


def step_contribution_to_json(sc: StepContribution) -> JSONObject:
    """Serialize :class:`StepContribution` to a JSON-compatible dict."""
    return {
        "stepId": sc.step_id,
        "searchName": sc.search_name,
        "baselineRecall": round(sc.baseline_recall, 4),
        "ablatedRecall": round(sc.ablated_recall, 4),
        "recallDelta": round(sc.recall_delta, 4),
        "baselineFpr": round(sc.baseline_fpr, 4),
        "ablatedFpr": round(sc.ablated_fpr, 4),
        "fprDelta": round(sc.fpr_delta, 4),
        "verdict": sc.verdict,
        "enrichmentDelta": round(sc.enrichment_delta, 4),
        "narrative": sc.narrative,
    }


def parameter_sweep_point_to_json(p: ParameterSweepPoint) -> JSONObject:
    """Serialize :class:`ParameterSweepPoint` to a JSON-compatible dict."""
    return {
        "value": p.value,
        "positiveHits": p.positive_hits,
        "negativeHits": p.negative_hits,
        "totalResults": p.total_results,
        "recall": round(p.recall, 4),
        "fpr": round(p.fpr, 4),
        "f1": round(p.f1, 4),
    }


def parameter_sensitivity_to_json(ps: ParameterSensitivity) -> JSONObject:
    """Serialize :class:`ParameterSensitivity` to a JSON-compatible dict."""
    return {
        "stepId": ps.step_id,
        "paramName": ps.param_name,
        "currentValue": ps.current_value,
        "sweepPoints": [parameter_sweep_point_to_json(p) for p in ps.sweep_points],
        "recommendedValue": ps.recommended_value,
        "recommendation": ps.recommendation,
    }


def step_analysis_to_json(sa: StepAnalysisResult) -> JSONObject:
    """Serialize :class:`StepAnalysisResult` to a JSON-compatible dict."""
    return {
        "stepEvaluations": [step_evaluation_to_json(e) for e in sa.step_evaluations],
        "operatorComparisons": [
            operator_comparison_to_json(c) for c in sa.operator_comparisons
        ],
        "stepContributions": [
            step_contribution_to_json(c) for c in sa.step_contributions
        ],
        "parameterSensitivities": [
            parameter_sensitivity_to_json(s) for s in sa.parameter_sensitivities
        ],
    }


def experiment_to_json(exp: Experiment) -> JSONObject:
    """Serialize a full :class:`Experiment` to a JSON-compatible dict."""
    config: JSONObject = {
        "siteId": exp.config.site_id,
        "recordType": exp.config.record_type,
        "mode": exp.config.mode,
        "searchName": exp.config.search_name,
        "parameters": exp.config.parameters,
        "positiveControls": list(exp.config.positive_controls),
        "negativeControls": list(exp.config.negative_controls),
        "controlsSearchName": exp.config.controls_search_name,
        "controlsParamName": exp.config.controls_param_name,
        "controlsValueFormat": exp.config.controls_value_format,
        "enableCrossValidation": exp.config.enable_cross_validation,
        "kFolds": exp.config.k_folds,
        "enrichmentTypes": list(exp.config.enrichment_types),
        "name": exp.config.name,
        "description": exp.config.description,
        "optimizationBudget": exp.config.optimization_budget,
        "optimizationObjective": exp.config.optimization_objective,
    }
    if exp.config.step_tree is not None:
        config["stepTree"] = exp.config.step_tree
    if exp.config.source_strategy_id:
        config["sourceStrategyId"] = exp.config.source_strategy_id
    if exp.config.optimization_target_step:
        config["optimizationTargetStep"] = exp.config.optimization_target_step
    if exp.config.enable_step_analysis:
        config["enableStepAnalysis"] = True
        config["stepAnalysisPhases"] = list(exp.config.step_analysis_phases)
    if exp.config.optimization_specs:
        config["optimizationSpecs"] = [
            {
                "name": s.name,
                "type": s.type,
                "min": s.min,
                "max": s.max,
                "step": s.step,
                "choices": cast(JSONValue, s.choices),
            }
            for s in exp.config.optimization_specs
        ]
    if exp.config.parameter_display_values:
        config["parameterDisplayValues"] = cast(
            JSONObject, exp.config.parameter_display_values
        )
    if exp.config.control_set_id:
        config["controlSetId"] = exp.config.control_set_id
    if exp.config.threshold_knobs:
        config["thresholdKnobs"] = [
            {
                "stepId": k.step_id,
                "paramName": k.param_name,
                "minVal": k.min_val,
                "maxVal": k.max_val,
                "stepSize": k.step_size,
            }
            for k in exp.config.threshold_knobs
        ]
    if exp.config.operator_knobs:
        config["operatorKnobs"] = [
            {"combineNodeId": k.combine_node_id, "options": list(k.options)}
            for k in exp.config.operator_knobs
        ]
    if exp.config.threshold_knobs or exp.config.operator_knobs:
        config["treeOptimizationObjective"] = exp.config.tree_optimization_objective
        config["treeOptimizationBudget"] = exp.config.tree_optimization_budget
        if exp.config.max_list_size is not None:
            config["maxListSize"] = exp.config.max_list_size
    if exp.config.sort_attribute:
        config["sortAttribute"] = exp.config.sort_attribute
        config["sortDirection"] = exp.config.sort_direction
    if exp.config.parent_experiment_id:
        config["parentExperimentId"] = exp.config.parent_experiment_id

    result: JSONObject = {
        "id": exp.id,
        "config": config,
        "status": exp.status,
        "metrics": metrics_to_json(exp.metrics) if exp.metrics else None,
        "crossValidation": (
            cv_result_to_json(exp.cross_validation) if exp.cross_validation else None
        ),
        "enrichmentResults": [
            enrichment_result_to_json(er) for er in exp.enrichment_results
        ],
        "truePositiveGenes": [gene_info_to_json(g) for g in exp.true_positive_genes],
        "falseNegativeGenes": [gene_info_to_json(g) for g in exp.false_negative_genes],
        "falsePositiveGenes": [gene_info_to_json(g) for g in exp.false_positive_genes],
        "trueNegativeGenes": [gene_info_to_json(g) for g in exp.true_negative_genes],
        "error": exp.error,
        "totalTimeSeconds": (
            round(exp.total_time_seconds, 2) if exp.total_time_seconds else None
        ),
        "createdAt": exp.created_at,
        "completedAt": exp.completed_at,
        "batchId": exp.batch_id,
        "benchmarkId": exp.benchmark_id,
        "controlSetLabel": exp.control_set_label,
        "isPrimaryBenchmark": exp.is_primary_benchmark,
        "optimizationResult": exp.optimization_result,
        "wdkStrategyId": exp.wdk_strategy_id,
        "wdkStepId": exp.wdk_step_id,
        "notes": exp.notes,
        "stepAnalysis": (
            step_analysis_to_json(exp.step_analysis) if exp.step_analysis else None
        ),
        "rankMetrics": (
            rank_metrics_to_json(exp.rank_metrics) if exp.rank_metrics else None
        ),
        "robustness": (
            bootstrap_result_to_json(exp.robustness) if exp.robustness else None
        ),
        "treeOptimization": (
            tree_optimization_result_to_json(exp.tree_optimization)
            if exp.tree_optimization
            else None
        ),
    }
    return result


def experiment_summary_to_json(exp: Experiment) -> JSONObject:
    """Serialize an experiment to a lightweight summary dict."""
    return {
        "id": exp.id,
        "name": exp.config.name,
        "siteId": exp.config.site_id,
        "searchName": exp.config.search_name,
        "recordType": exp.config.record_type,
        "mode": exp.config.mode,
        "status": exp.status,
        "f1Score": round(exp.metrics.f1_score, 4) if exp.metrics else None,
        "sensitivity": round(exp.metrics.sensitivity, 4) if exp.metrics else None,
        "specificity": round(exp.metrics.specificity, 4) if exp.metrics else None,
        "totalPositives": len(exp.config.positive_controls),
        "totalNegatives": len(exp.config.negative_controls),
        "createdAt": exp.created_at,
        "batchId": exp.batch_id,
        "benchmarkId": exp.benchmark_id,
        "controlSetLabel": exp.control_set_label,
        "isPrimaryBenchmark": exp.is_primary_benchmark,
    }
