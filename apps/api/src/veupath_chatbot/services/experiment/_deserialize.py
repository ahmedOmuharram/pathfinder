"""Deserialize JSON dicts back into Experiment dataclass trees."""

from __future__ import annotations

from typing import Any, cast

from veupath_chatbot.services.experiment.types import (
    BootstrapResult,
    ConfidenceInterval,
    ConfusionMatrix,
    ControlValueFormat,
    CrossValidationResult,
    EnrichmentResult,
    EnrichmentTerm,
    Experiment,
    ExperimentConfig,
    ExperimentMetrics,
    FoldMetrics,
    GeneInfo,
    NegativeSetVariant,
    OperatorComparison,
    OperatorKnob,
    OperatorVariant,
    OptimizationSpec,
    ParameterSensitivity,
    ParameterSweepPoint,
    RankMetrics,
    StepAnalysisResult,
    StepContribution,
    StepContributionVerdict,
    StepEvaluation,
    ThresholdKnob,
    TreeOptimizationResult,
    TreeOptimizationTrial,
)


def _metrics_from_json(d: dict[str, Any]) -> ExperimentMetrics:
    cm = d["confusionMatrix"]
    return ExperimentMetrics(
        confusion_matrix=ConfusionMatrix(
            true_positives=cm["truePositives"],
            false_positives=cm["falsePositives"],
            true_negatives=cm["trueNegatives"],
            false_negatives=cm["falseNegatives"],
        ),
        sensitivity=d["sensitivity"],
        specificity=d["specificity"],
        precision=d["precision"],
        negative_predictive_value=d.get("negativePredictiveValue", 0),
        false_positive_rate=d.get("falsePositiveRate", 0),
        false_negative_rate=d.get("falseNegativeRate", 0),
        f1_score=d["f1Score"],
        mcc=d["mcc"],
        balanced_accuracy=d["balancedAccuracy"],
        youdens_j=d.get("youdensJ", 0),
        total_results=d.get("totalResults", 0),
        total_positives=d.get("totalPositives", 0),
        total_negatives=d.get("totalNegatives", 0),
    )


def _gene_from_json(d: dict[str, Any]) -> GeneInfo:
    return GeneInfo(
        id=d["id"],
        name=d.get("name"),
        organism=d.get("organism"),
        product=d.get("product"),
    )


def _cv_from_json(d: dict[str, Any]) -> CrossValidationResult:
    return CrossValidationResult(
        k=d["k"],
        folds=[
            FoldMetrics(
                fold_index=f["foldIndex"],
                metrics=_metrics_from_json(f["metrics"]),
                positive_control_ids=f.get("positiveControlIds", []),
                negative_control_ids=f.get("negativeControlIds", []),
            )
            for f in d.get("folds", [])
        ],
        mean_metrics=_metrics_from_json(d["meanMetrics"]),
        std_metrics=d.get("stdMetrics", {}),
        overfitting_score=d.get("overfittingScore", 0),
        overfitting_level=d.get("overfittingLevel", "low"),
    )


def _enrichment_from_json(d: dict[str, Any]) -> EnrichmentResult:
    return EnrichmentResult(
        analysis_type=d["analysisType"],
        terms=[
            EnrichmentTerm(
                term_id=t["termId"],
                term_name=t["termName"],
                gene_count=t["geneCount"],
                background_count=t["backgroundCount"],
                fold_enrichment=t["foldEnrichment"],
                odds_ratio=t["oddsRatio"],
                p_value=t["pValue"],
                fdr=t["fdr"],
                bonferroni=t["bonferroni"],
                genes=t.get("genes", []),
            )
            for t in d.get("terms", [])
        ],
        total_genes_analyzed=d.get("totalGenesAnalyzed", 0),
        background_size=d.get("backgroundSize", 0),
    )


def _step_evaluation_from_json(d: dict[str, Any]) -> StepEvaluation:
    return StepEvaluation(
        step_id=d["stepId"],
        search_name=d["searchName"],
        display_name=d["displayName"],
        result_count=d["resultCount"],
        positive_hits=d["positiveHits"],
        positive_total=d["positiveTotal"],
        negative_hits=d["negativeHits"],
        negative_total=d["negativeTotal"],
        recall=d["recall"],
        false_positive_rate=d["falsePositiveRate"],
        captured_positive_ids=d.get("capturedPositiveIds", []),
        captured_negative_ids=d.get("capturedNegativeIds", []),
        tp_movement=d.get("tpMovement", 0),
        fp_movement=d.get("fpMovement", 0),
        fn_movement=d.get("fnMovement", 0),
    )


def _operator_variant_from_json(d: dict[str, Any]) -> OperatorVariant:
    return OperatorVariant(
        operator=d["operator"],
        positive_hits=d["positiveHits"],
        negative_hits=d["negativeHits"],
        total_results=d["totalResults"],
        recall=d["recall"],
        false_positive_rate=d["falsePositiveRate"],
        f1_score=d["f1Score"],
    )


def _operator_comparison_from_json(d: dict[str, Any]) -> OperatorComparison:
    return OperatorComparison(
        combine_node_id=d["combineNodeId"],
        current_operator=d["currentOperator"],
        variants=[_operator_variant_from_json(v) for v in d.get("variants", [])],
        recommendation=d.get("recommendation", ""),
        recommended_operator=d.get("recommendedOperator", ""),
        precision_at_k_delta={
            int(k): v for k, v in d.get("precisionAtKDelta", {}).items()
        },
    )


def _step_contribution_from_json(d: dict[str, Any]) -> StepContribution:
    return StepContribution(
        step_id=d["stepId"],
        search_name=d["searchName"],
        baseline_recall=d["baselineRecall"],
        ablated_recall=d["ablatedRecall"],
        recall_delta=d["recallDelta"],
        baseline_fpr=d["baselineFpr"],
        ablated_fpr=d["ablatedFpr"],
        fpr_delta=d["fprDelta"],
        verdict=cast(StepContributionVerdict, d["verdict"]),
        enrichment_delta=d.get("enrichmentDelta", 0.0),
        narrative=d.get("narrative", ""),
    )


def _sweep_point_from_json(d: dict[str, Any]) -> ParameterSweepPoint:
    return ParameterSweepPoint(
        value=d["value"],
        positive_hits=d["positiveHits"],
        negative_hits=d["negativeHits"],
        total_results=d["totalResults"],
        recall=d["recall"],
        fpr=d["fpr"],
        f1=d["f1"],
    )


def _parameter_sensitivity_from_json(d: dict[str, Any]) -> ParameterSensitivity:
    return ParameterSensitivity(
        step_id=d["stepId"],
        param_name=d["paramName"],
        current_value=d["currentValue"],
        sweep_points=[_sweep_point_from_json(p) for p in d.get("sweepPoints", [])],
        recommended_value=d.get("recommendedValue", 0.0),
        recommendation=d.get("recommendation", ""),
    )


def _step_analysis_from_json(d: dict[str, Any]) -> StepAnalysisResult:
    return StepAnalysisResult(
        step_evaluations=[
            _step_evaluation_from_json(e) for e in d.get("stepEvaluations", [])
        ],
        operator_comparisons=[
            _operator_comparison_from_json(c) for c in d.get("operatorComparisons", [])
        ],
        step_contributions=[
            _step_contribution_from_json(c) for c in d.get("stepContributions", [])
        ],
        parameter_sensitivities=[
            _parameter_sensitivity_from_json(s)
            for s in d.get("parameterSensitivities", [])
        ],
    )


def _rank_metrics_from_json(d: dict[str, Any]) -> RankMetrics:
    return RankMetrics(
        precision_at_k={int(k): v for k, v in d.get("precisionAtK", {}).items()},
        recall_at_k={int(k): v for k, v in d.get("recallAtK", {}).items()},
        enrichment_at_k={int(k): v for k, v in d.get("enrichmentAtK", {}).items()},
        pr_curve=[(p, r) for p, r in d.get("prCurve", [])],
        list_size_vs_recall=[(s, r) for s, r in d.get("listSizeVsRecall", [])],
        total_results=d.get("totalResults", 0),
    )


def _ci_from_json(d: dict[str, Any]) -> ConfidenceInterval:
    return ConfidenceInterval(
        lower=d.get("lower", 0),
        mean=d.get("mean", 0),
        upper=d.get("upper", 0),
        std=d.get("std", 0),
    )


def _bootstrap_from_json(d: dict[str, Any]) -> BootstrapResult:
    return BootstrapResult(
        n_iterations=d.get("nIterations", 0),
        metric_cis={k: _ci_from_json(v) for k, v in d.get("metricCis", {}).items()},
        rank_metric_cis={
            k: _ci_from_json(v) for k, v in d.get("rankMetricCis", {}).items()
        },
        top_k_stability=d.get("topKStability", 0),
        negative_set_sensitivity=[
            NegativeSetVariant(
                label=v["label"],
                negative_count=v.get("negativeCount", 0),
                rank_metrics=_rank_metrics_from_json(v["rankMetrics"]),
            )
            for v in d.get("negativeSetSensitivity", [])
        ],
    )


def _tree_opt_from_json(d: dict[str, Any]) -> TreeOptimizationResult:
    best = d.get("bestTrial")
    return TreeOptimizationResult(
        best_trial=TreeOptimizationTrial(
            trial_number=best["trialNumber"],
            parameters=best.get("parameters", {}),
            score=best.get("score", 0),
            rank_metrics=_rank_metrics_from_json(best["rankMetrics"])
            if best.get("rankMetrics")
            else None,
            list_size=best.get("listSize", 0),
        )
        if best
        else None,
        all_trials=[
            TreeOptimizationTrial(
                trial_number=t["trialNumber"],
                parameters=t.get("parameters", {}),
                score=t.get("score", 0),
                rank_metrics=_rank_metrics_from_json(t["rankMetrics"])
                if t.get("rankMetrics")
                else None,
                list_size=t.get("listSize", 0),
            )
            for t in d.get("allTrials", [])
        ],
        total_time_seconds=d.get("totalTimeSeconds", 0),
        objective=d.get("objective", ""),
    )


def experiment_from_json(d: dict[str, Any]) -> Experiment:
    """Reconstruct an :class:`Experiment` from its JSON representation.

    :param d: Dict produced by :func:`experiment_to_json`.
    :returns: Fully hydrated Experiment dataclass.
    """
    cfg = d["config"]

    opt_specs = None
    raw_specs = cfg.get("optimizationSpecs")
    if raw_specs and isinstance(raw_specs, list):
        opt_specs = [
            OptimizationSpec(
                name=s["name"],
                type=s["type"],
                min=s.get("min"),
                max=s.get("max"),
                step=s.get("step"),
                choices=s.get("choices"),
            )
            for s in raw_specs
        ]

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
            ControlValueFormat, cfg.get("controlsValueFormat", "newline")
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
            [
                "step_evaluation",
                "operator_comparison",
                "contribution",
                "sensitivity",
            ],
        ),
        control_set_id=cfg.get("controlSetId"),
        threshold_knobs=[
            ThresholdKnob(
                step_id=k["stepId"],
                param_name=k["paramName"],
                min_val=k["minVal"],
                max_val=k["maxVal"],
                step_size=k.get("stepSize"),
            )
            for k in cfg.get("thresholdKnobs", [])
        ]
        or None,
        operator_knobs=[
            OperatorKnob(
                combine_node_id=k["combineNodeId"],
                options=k.get("options", ["INTERSECT", "UNION", "MINUS"]),
            )
            for k in cfg.get("operatorKnobs", [])
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
        status=d.get("status", "completed"),
        created_at=d.get("createdAt", ""),
        completed_at=d.get("completedAt"),
    )

    if d.get("metrics"):
        exp.metrics = _metrics_from_json(d["metrics"])
    if d.get("crossValidation"):
        exp.cross_validation = _cv_from_json(d["crossValidation"])

    exp.enrichment_results = [
        _enrichment_from_json(er) for er in d.get("enrichmentResults", [])
    ]
    exp.true_positive_genes = [
        _gene_from_json(g) for g in d.get("truePositiveGenes", [])
    ]
    exp.false_negative_genes = [
        _gene_from_json(g) for g in d.get("falseNegativeGenes", [])
    ]
    exp.false_positive_genes = [
        _gene_from_json(g) for g in d.get("falsePositiveGenes", [])
    ]
    exp.true_negative_genes = [
        _gene_from_json(g) for g in d.get("trueNegativeGenes", [])
    ]
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

    if d.get("stepAnalysis"):
        exp.step_analysis = _step_analysis_from_json(d["stepAnalysis"])
    if d.get("rankMetrics"):
        exp.rank_metrics = _rank_metrics_from_json(d["rankMetrics"])
    if d.get("robustness"):
        exp.robustness = _bootstrap_from_json(d["robustness"])
    if d.get("treeOptimization"):
        exp.tree_optimization = _tree_opt_from_json(d["treeOptimization"])

    return exp
