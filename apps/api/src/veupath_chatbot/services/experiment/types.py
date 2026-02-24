"""Shared data types for the Experiment Lab."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from veupath_chatbot.platform.types import JSONObject

EnrichmentAnalysisType = Literal[
    "go_function", "go_component", "go_process", "pathway", "word"
]

ExperimentStatus = Literal["pending", "running", "completed", "error", "cancelled"]

ExperimentProgressPhase = Literal[
    "started",
    "evaluating",
    "optimizing",
    "cross_validating",
    "enriching",
    "completed",
    "error",
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
    type: str  # "numeric" | "integer" | "categorical"
    min: float | None = None
    max: float | None = None
    step: float | None = None
    choices: list[str] | None = None


@dataclass(slots=True)
class ExperimentConfig:
    """Full configuration for an experiment run."""

    site_id: str
    record_type: str
    search_name: str
    parameters: JSONObject
    positive_controls: list[str]
    negative_controls: list[str]
    controls_search_name: str
    controls_param_name: str
    controls_value_format: str = "newline"
    enable_cross_validation: bool = False
    k_folds: int = 5
    enrichment_types: list[EnrichmentAnalysisType] = field(default_factory=list)
    name: str = ""
    description: str = ""
    optimization_specs: list[OptimizationSpec] | None = None
    optimization_budget: int = 30
    optimization_objective: str = "balanced_accuracy"
    parameter_display_values: dict[str, str] | None = None


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
    optimization_result: JSONObject | None = None
    wdk_strategy_id: int | None = None
    wdk_step_id: int | None = None
    notes: str | None = None


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


def experiment_to_json(exp: Experiment) -> JSONObject:
    """Serialize a full :class:`Experiment` to a JSON-compatible dict."""
    config: JSONObject = {
        "siteId": exp.config.site_id,
        "recordType": exp.config.record_type,
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
    if exp.config.optimization_specs:
        config["optimizationSpecs"] = [
            {
                "name": s.name,
                "type": s.type,
                "min": s.min,
                "max": s.max,
                "step": s.step,
                "choices": s.choices,
            }
            for s in exp.config.optimization_specs
        ]
    if exp.config.parameter_display_values:
        config["parameterDisplayValues"] = exp.config.parameter_display_values

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
        "optimizationResult": exp.optimization_result,
        "wdkStrategyId": exp.wdk_strategy_id,
        "wdkStepId": exp.wdk_step_id,
        "notes": exp.notes,
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
        "status": exp.status,
        "f1Score": round(exp.metrics.f1_score, 4) if exp.metrics else None,
        "sensitivity": round(exp.metrics.sensitivity, 4) if exp.metrics else None,
        "specificity": round(exp.metrics.specificity, 4) if exp.metrics else None,
        "totalPositives": len(exp.config.positive_controls),
        "totalNegatives": len(exp.config.negative_controls),
        "createdAt": exp.created_at,
    }
