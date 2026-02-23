"""K-fold cross-validation for overfitting detection.

Splits positive and negative control gene lists into k folds,
evaluates each held-out fold, and aggregates metrics to detect
overfitting.
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable, Coroutine
from typing import Any

from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.control_tests import run_positive_negative_controls
from veupath_chatbot.services.experiment.metrics import (
    compute_confusion_matrix,
    compute_metrics,
    metrics_from_control_result,
)
from veupath_chatbot.services.experiment.types import (
    ConfusionMatrix,
    CrossValidationResult,
    ExperimentMetrics,
    FoldMetrics,
)

logger = get_logger(__name__)

ProgressCallback = Callable[[int, int], Coroutine[Any, Any, None]]
"""Async callback(fold_index, total_folds) for progress reporting."""


def _stratified_kfold(ids: list[str], k: int, seed: int = 42) -> list[list[str]]:
    """Split a list into k roughly equal folds (deterministic)."""
    shuffled = list(ids)
    rng = random.Random(seed)
    rng.shuffle(shuffled)
    folds: list[list[str]] = [[] for _ in range(k)]
    for i, item in enumerate(shuffled):
        folds[i % k].append(item)
    return folds


def _average_metrics(fold_metrics_list: list[ExperimentMetrics]) -> ExperimentMetrics:
    """Compute element-wise mean of a list of metrics."""
    n = len(fold_metrics_list)
    if n == 0:
        cm = ConfusionMatrix(0, 0, 0, 0)
        return compute_metrics(cm)

    def _mean(getter: Callable[[ExperimentMetrics], float]) -> float:
        return sum(getter(m) for m in fold_metrics_list) / n

    cm = ConfusionMatrix(
        true_positives=round(_mean(lambda m: m.confusion_matrix.true_positives)),
        false_positives=round(_mean(lambda m: m.confusion_matrix.false_positives)),
        true_negatives=round(_mean(lambda m: m.confusion_matrix.true_negatives)),
        false_negatives=round(_mean(lambda m: m.confusion_matrix.false_negatives)),
    )

    return ExperimentMetrics(
        confusion_matrix=cm,
        sensitivity=_mean(lambda m: m.sensitivity),
        specificity=_mean(lambda m: m.specificity),
        precision=_mean(lambda m: m.precision),
        negative_predictive_value=_mean(lambda m: m.negative_predictive_value),
        false_positive_rate=_mean(lambda m: m.false_positive_rate),
        false_negative_rate=_mean(lambda m: m.false_negative_rate),
        f1_score=_mean(lambda m: m.f1_score),
        mcc=_mean(lambda m: m.mcc),
        balanced_accuracy=_mean(lambda m: m.balanced_accuracy),
        youdens_j=_mean(lambda m: m.youdens_j),
        total_results=round(_mean(lambda m: m.total_results)),
        total_positives=round(_mean(lambda m: m.total_positives)),
        total_negatives=round(_mean(lambda m: m.total_negatives)),
    )


def _std_metrics(
    fold_metrics_list: list[ExperimentMetrics],
    mean: ExperimentMetrics,
) -> dict[str, float]:
    """Compute std deviation for key metrics across folds."""
    n = len(fold_metrics_list)
    if n < 2:
        return {}

    fields = [
        ("sensitivity", lambda m: m.sensitivity),
        ("specificity", lambda m: m.specificity),
        ("precision", lambda m: m.precision),
        ("f1Score", lambda m: m.f1_score),
        ("mcc", lambda m: m.mcc),
        ("balancedAccuracy", lambda m: m.balanced_accuracy),
    ]

    result: dict[str, float] = {}
    for name, getter in fields:
        mean_val = getter(mean)
        variance = sum((getter(m) - mean_val) ** 2 for m in fold_metrics_list) / n
        result[name] = math.sqrt(variance)
    return result


def _compute_overfitting_score(
    full_metrics: ExperimentMetrics,
    mean_holdout: ExperimentMetrics,
) -> tuple[float, str]:
    """Estimate overfitting from the gap between full-set and holdout metrics.

    :returns: (score, level) where score is 0-1 and level is low/moderate/high.
    """
    f1_gap = abs(full_metrics.f1_score - mean_holdout.f1_score)
    sens_gap = abs(full_metrics.sensitivity - mean_holdout.sensitivity)
    spec_gap = abs(full_metrics.specificity - mean_holdout.specificity)

    score = (f1_gap + sens_gap + spec_gap) / 3.0

    if score < 0.1:
        level = "low"
    elif score < 0.25:
        level = "moderate"
    else:
        level = "high"
    return score, level


async def run_cross_validation(
    *,
    site_id: str,
    record_type: str,
    search_name: str,
    parameters: JSONObject,
    controls_search_name: str,
    controls_param_name: str,
    positive_controls: list[str],
    negative_controls: list[str],
    controls_value_format: str = "newline",
    k: int = 5,
    full_metrics: ExperimentMetrics | None = None,
    progress_callback: ProgressCallback | None = None,
) -> CrossValidationResult:
    """Run k-fold cross-validation on control gene lists.

    :param site_id: VEuPathDB site.
    :param record_type: WDK record type.
    :param search_name: WDK search to evaluate.
    :param parameters: Fixed search parameters.
    :param controls_search_name: Search that accepts control IDs.
    :param controls_param_name: Parameter name for the ID list.
    :param positive_controls: Known-positive gene IDs.
    :param negative_controls: Known-negative gene IDs.
    :param controls_value_format: Format for encoding ID lists.
    :param k: Number of folds.
    :param full_metrics: Pre-computed full-set metrics (for overfitting comparison).
    :param progress_callback: Optional progress reporter.
    :returns: Cross-validation result with per-fold and aggregate metrics.
    """
    k = max(2, min(k, len(positive_controls), len(negative_controls)))

    pos_folds = _stratified_kfold(positive_controls, k)
    neg_folds = _stratified_kfold(negative_controls, k)

    fold_results: list[FoldMetrics] = []

    for fold_idx in range(k):
        holdout_pos = pos_folds[fold_idx]
        holdout_neg = neg_folds[fold_idx]

        if progress_callback:
            await progress_callback(fold_idx, k)

        try:
            result = await run_positive_negative_controls(
                site_id=site_id,
                record_type=record_type,
                target_search_name=search_name,
                target_parameters=parameters,
                controls_search_name=controls_search_name,
                controls_param_name=controls_param_name,
                positive_controls=holdout_pos if holdout_pos else None,
                negative_controls=holdout_neg if holdout_neg else None,
                controls_value_format=controls_value_format,
            )
            fold_metrics = metrics_from_control_result(result)
        except Exception as exc:
            logger.warning("Fold %d failed: %s", fold_idx, exc)
            cm = compute_confusion_matrix(
                positive_hits=0,
                total_positives=len(holdout_pos),
                negative_hits=0,
                total_negatives=len(holdout_neg),
            )
            fold_metrics = compute_metrics(cm)

        fold_results.append(
            FoldMetrics(
                fold_index=fold_idx,
                metrics=fold_metrics,
                positive_control_ids=holdout_pos,
                negative_control_ids=holdout_neg,
            )
        )

    metrics_list = [f.metrics for f in fold_results]
    mean = _average_metrics(metrics_list)
    std = _std_metrics(metrics_list, mean)

    if full_metrics is not None:
        ov_score, ov_level = _compute_overfitting_score(full_metrics, mean)
    else:
        ov_score, ov_level = 0.0, "low"

    return CrossValidationResult(
        k=k,
        folds=fold_results,
        mean_metrics=mean,
        std_metrics=std,
        overfitting_score=ov_score,
        overfitting_level=ov_level,
    )
