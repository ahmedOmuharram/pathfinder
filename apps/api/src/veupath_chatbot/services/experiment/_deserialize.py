"""Deserialize JSON dicts back into Experiment dataclass trees.

Simple sub-types are deserialized via the generic ``from_json`` converter.
Only ``Experiment`` / ``ExperimentConfig`` require hand-written logic due
to conditional field defaults and enrichment deduplication.
"""

from typing import Any, cast

from veupath_chatbot.services.experiment.types import (
    BootstrapResult,
    ControlValueFormat,
    CrossValidationResult,
    EnrichmentResult,
    Experiment,
    ExperimentConfig,
    ExperimentMetrics,
    GeneInfo,
    OperatorKnob,
    OptimizationSpec,
    RankMetrics,
    StepAnalysisResult,
    ThresholdKnob,
    TreeOptimizationResult,
)
from veupath_chatbot.services.experiment.types.core import DEFAULT_STEP_ANALYSIS_PHASES
from veupath_chatbot.services.experiment.types.json_codec import from_json


def experiment_from_json(d: dict[str, Any]) -> Experiment:
    """Reconstruct an :class:`Experiment` from its JSON representation.

    :param d: Dict produced by :func:`experiment_to_json`.
    :returns: Fully hydrated Experiment dataclass.
    """
    cfg = d["config"]

    opt_specs = None
    raw_specs = cfg.get("optimizationSpecs")
    if raw_specs and isinstance(raw_specs, list):
        opt_specs = [from_json(s, OptimizationSpec) for s in raw_specs]

    config = ExperimentConfig(
        site_id=cfg["siteId"],
        record_type=cfg["recordType"],
        search_name=cfg.get("searchName", ""),
        parameters=cfg.get("parameters", {}),
        positive_controls=cfg.get("positiveControls", []),
        negative_controls=cfg.get("negativeControls", []),
        controls_search_name=cfg.get("controlsSearchName", ""),
        controls_param_name=cfg.get("controlsParamName", ""),
        controls_value_format=cast(
            "ControlValueFormat", cfg.get("controlsValueFormat", "newline")
        ),
        enable_cross_validation=cfg.get("enableCrossValidation", False),
        k_folds=cfg.get("kFolds", 5),
        enrichment_types=cfg.get("enrichmentTypes", []),
        name=cfg.get("name", ""),
        description=cfg.get("description", ""),
        mode=cfg.get("mode", "single"),
        step_tree=cfg.get("stepTree"),
        source_strategy_id=cfg.get("sourceStrategyId"),
        optimization_target_step=cfg.get("optimizationTargetStep"),
        optimization_specs=opt_specs,
        optimization_budget=cfg.get("optimizationBudget", 30),
        optimization_objective=cfg.get("optimizationObjective", "balanced_accuracy"),
        parameter_display_values=cfg.get("parameterDisplayValues"),
        enable_step_analysis=cfg.get("enableStepAnalysis", False),
        step_analysis_phases=cfg.get(
            "stepAnalysisPhases",
            list(DEFAULT_STEP_ANALYSIS_PHASES),
        ),
        control_set_id=cfg.get("controlSetId"),
        # BUG FIX: cfg.get("thresholdKnobs") could be None (not just missing),
        # which would cause TypeError when iterated. Guard with `or []`.
        threshold_knobs=[
            from_json(k, ThresholdKnob) for k in (cfg.get("thresholdKnobs") or [])
        ]
        or None,
        operator_knobs=[
            from_json(k, OperatorKnob) for k in (cfg.get("operatorKnobs") or [])
        ]
        or None,
        tree_optimization_objective=cfg.get(
            "treeOptimizationObjective", "precision_at_50"
        ),
        tree_optimization_budget=cfg.get("treeOptimizationBudget", 50),
        max_list_size=cfg.get("maxListSize"),
        sort_attribute=cfg.get("sortAttribute"),
        sort_direction=cfg.get("sortDirection", "ASC"),
        parent_experiment_id=cfg.get("parentExperimentId"),
    )

    exp = Experiment(
        id=d["id"],
        config=config,
        user_id=d.get("userId"),
        status=d.get("status", "completed"),
        created_at=d.get("createdAt", ""),
        completed_at=d.get("completedAt"),
    )

    if d.get("metrics"):
        exp.metrics = from_json(d["metrics"], ExperimentMetrics)
    if d.get("crossValidation"):
        exp.cross_validation = from_json(d["crossValidation"], CrossValidationResult)

    # Deduplicate enrichment results by analysis_type, keeping the last
    # (most recent) entry.  This cleans up data persisted before the
    # upsert_enrichment_result helper was introduced.
    _seen_types: dict[str, int] = {}
    _all_er = [from_json(er, EnrichmentResult) for er in d.get("enrichmentResults", [])]
    for i, er in enumerate(_all_er):
        _seen_types[er.analysis_type] = i
    exp.enrichment_results = [_all_er[i] for i in sorted(_seen_types.values())]

    for attr, key in (
        ("true_positive_genes", "truePositiveGenes"),
        ("false_negative_genes", "falseNegativeGenes"),
        ("false_positive_genes", "falsePositiveGenes"),
        ("true_negative_genes", "trueNegativeGenes"),
    ):
        setattr(exp, attr, [from_json(g, GeneInfo) for g in d.get(key, [])])
    exp.error = d.get("error")
    exp.total_time_seconds = d.get("totalTimeSeconds")
    exp.batch_id = d.get("batchId")
    exp.benchmark_id = d.get("benchmarkId")
    exp.control_set_label = d.get("controlSetLabel")
    exp.is_primary_benchmark = d.get("isPrimaryBenchmark", False)
    exp.optimization_result = d.get("optimizationResult")
    exp.wdk_strategy_id = d.get("wdkStrategyId")
    exp.wdk_step_id = d.get("wdkStepId")
    exp.notes = d.get("notes")

    for attr, key, cls in (
        ("step_analysis", "stepAnalysis", StepAnalysisResult),
        ("rank_metrics", "rankMetrics", RankMetrics),
        ("robustness", "robustness", BootstrapResult),
        ("tree_optimization", "treeOptimization", TreeOptimizationResult),
    ):
        raw = d.get(key)
        if raw:
            setattr(exp, attr, from_json(raw, cls))

    return exp
