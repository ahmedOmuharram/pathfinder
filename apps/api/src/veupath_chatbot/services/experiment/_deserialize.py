"""Deserialize JSON dicts back into Experiment dataclass trees."""

from __future__ import annotations

from veupath_chatbot.services.experiment.types import (
    ConfusionMatrix,
    CrossValidationResult,
    EnrichmentResult,
    EnrichmentTerm,
    Experiment,
    ExperimentConfig,
    ExperimentMetrics,
    FoldMetrics,
    GeneInfo,
)


def _metrics_from_json(d: dict) -> ExperimentMetrics:
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


def _gene_from_json(d: dict) -> GeneInfo:
    return GeneInfo(
        id=d["id"],
        name=d.get("name"),
        organism=d.get("organism"),
        product=d.get("product"),
    )


def _cv_from_json(d: dict) -> CrossValidationResult:
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


def _enrichment_from_json(d: dict) -> EnrichmentResult:
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


def experiment_from_json(d: dict) -> Experiment:
    """Reconstruct an :class:`Experiment` from its JSON representation.

    :param d: Dict produced by :func:`experiment_to_json`.
    :returns: Fully hydrated Experiment dataclass.
    """
    cfg = d["config"]

    config = ExperimentConfig(
        site_id=cfg["siteId"],
        record_type=cfg["recordType"],
        search_name=cfg["searchName"],
        parameters=cfg.get("parameters", {}),
        positive_controls=cfg.get("positiveControls", []),
        negative_controls=cfg.get("negativeControls", []),
        controls_search_name=cfg.get("controlsSearchName", ""),
        controls_param_name=cfg.get("controlsParamName", ""),
        controls_value_format=cfg.get("controlsValueFormat", "newline"),
        enable_cross_validation=cfg.get("enableCrossValidation", False),
        k_folds=cfg.get("kFolds", 5),
        enrichment_types=cfg.get("enrichmentTypes", []),
        name=cfg.get("name", ""),
        description=cfg.get("description", ""),
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

    return exp
