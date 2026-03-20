"""JSON serialization for experiment dataclasses.

Simple sub-types (metrics, enrichment, rank, step analysis, etc.) are
serialized via the generic ``to_json`` converter.  Only ``Experiment`` and
``ExperimentConfig`` require hand-written logic due to conditional field
inclusion and summary projections.
"""

from typing import cast

from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.experiment.types.experiment import Experiment
from veupath_chatbot.services.experiment.types.json_codec import to_json


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
        config["optimizationSpecs"] = to_json(exp.config.optimization_specs)
    if exp.config.parameter_display_values:
        config["parameterDisplayValues"] = cast(
            "JSONObject", exp.config.parameter_display_values
        )
    if exp.config.control_set_id:
        config["controlSetId"] = exp.config.control_set_id
    if exp.config.threshold_knobs:
        config["thresholdKnobs"] = to_json(exp.config.threshold_knobs)
    if exp.config.operator_knobs:
        config["operatorKnobs"] = to_json(exp.config.operator_knobs)
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
        "userId": exp.user_id,
        "config": config,
        "status": exp.status,
        "metrics": to_json(exp.metrics),
        "crossValidation": to_json(exp.cross_validation),
        "enrichmentResults": to_json(exp.enrichment_results),
        "truePositiveGenes": to_json(exp.true_positive_genes),
        "falseNegativeGenes": to_json(exp.false_negative_genes),
        "falsePositiveGenes": to_json(exp.false_positive_genes),
        "trueNegativeGenes": to_json(exp.true_negative_genes),
        "error": exp.error,
        "totalTimeSeconds": to_json(exp.total_time_seconds, _round=2),
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
        "stepAnalysis": to_json(exp.step_analysis),
        "rankMetrics": to_json(exp.rank_metrics),
        "robustness": to_json(exp.robustness),
        "treeOptimization": to_json(exp.tree_optimization),
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
