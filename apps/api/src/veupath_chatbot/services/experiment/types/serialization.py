"""JSON serialization functions for experiment dataclasses."""

from __future__ import annotations

from typing import cast

from veupath_chatbot.platform.types import JSONObject, JSONValue
from veupath_chatbot.services.experiment.types.enrichment import (
    EnrichmentResult,
    EnrichmentTerm,
)
from veupath_chatbot.services.experiment.types.experiment import Experiment
from veupath_chatbot.services.experiment.types.metrics import (
    CrossValidationResult,
    ExperimentMetrics,
    FoldMetrics,
    GeneInfo,
)
from veupath_chatbot.services.experiment.types.optimization import (
    TreeOptimizationResult,
    TreeOptimizationTrial,
)
from veupath_chatbot.services.experiment.types.rank import (
    BootstrapResult,
    ConfidenceInterval,
    NegativeSetVariant,
    RankMetrics,
)
from veupath_chatbot.services.experiment.types.step_analysis import (
    OperatorComparison,
    OperatorVariant,
    ParameterSensitivity,
    ParameterSweepPoint,
    StepAnalysisResult,
    StepContribution,
    StepEvaluation,
)


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
