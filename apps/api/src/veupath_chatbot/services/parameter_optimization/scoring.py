"""Scoring, analysis, and serialization helpers for parameter optimization."""

import warnings
from typing import cast

import optuna

from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject, JSONValue
from veupath_chatbot.services.parameter_optimization.config import (
    OptimizationConfig,
    OptimizationResult,
    ParameterSpec,
    TrialResult,
)

logger = get_logger(__name__)

_DEFAULT_TOTAL_GENES = 20_000
"""Fallback denominator when the total gene count is unknown."""

_MCC_ZERO_GUARD_EPSILON = 1e-10
_MIN_COMPLETED_TRIALS = 2


def _to_float(v: JSONValue) -> float | None:
    """Coerce JSON value to float for numeric comparisons."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    return None


def _to_int(v: JSONValue) -> int | None:
    """Coerce JSON value to int for counts."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return int(v)
    return None


def _score_mcc(r: float, specificity: float, raw_fpr: float) -> float:
    """Approximate MCC via TPR*TNR - FPR*FNR divided by sqrt of four products."""
    tpr, tnr, fpr_val, fnr = r, specificity, raw_fpr, 1.0 - r
    num = tpr * tnr - fpr_val * fnr
    denom = ((tpr + fpr_val) * (tpr + fnr) * (tnr + fpr_val) * (tnr + fnr)) ** 0.5
    return (num / denom) if denom > _MCC_ZERO_GUARD_EPSILON else 0.0


def _score_for_objective(
    r: float,
    precision: float,
    specificity: float,
    raw_fpr: float,
    cfg: OptimizationConfig,
) -> float:
    """Compute the raw (pre-penalty) score for *cfg.objective*."""
    f1_denom = precision + r
    fb_denom = cfg.beta**2 * precision + r
    scores: dict[str, float] = {
        "recall": r,
        "precision": precision,
        "specificity": specificity,
        "balanced_accuracy": (r + specificity) / 2.0,
        "mcc": _score_mcc(r, specificity, raw_fpr),
        "youdens_j": r + specificity - 1.0,
        "f1": (2 * precision * r / f1_denom) if f1_denom > 0 else 0.0,
        "f_beta": (
            ((1 + cfg.beta**2) * precision * r / fb_denom) if fb_denom > 0 else 0.0
        ),
        "custom": cfg.recall_weight * r - cfg.precision_weight * raw_fpr,
    }
    return scores.get(cfg.objective, r)


def _compute_score(
    recall: float | None,
    fpr: float | None,
    cfg: OptimizationConfig,
    *,
    result_count: int | None = None,
    positive_hits: int | None = None,
    negative_hits: int | None = None,
) -> float:
    r = recall if recall is not None else 0.0
    raw_fpr = fpr if fpr is not None else 0.0
    specificity = 1.0 - raw_fpr

    # True precision (PPV) = TP / (TP + FP). We approximate it from
    # intersection counts when available, falling back to specificity.
    if positive_hits is not None and negative_hits is not None:
        tp_fp = positive_hits + negative_hits
        precision = positive_hits / tp_fp if tp_fp > 0 else 0.0
    else:
        precision = specificity

    base = _score_for_objective(r, precision, specificity, raw_fpr, cfg)

    # Apply optional result-count penalty (tiebreaker for large result sets).
    if cfg.result_count_penalty > 0 and result_count is not None and result_count > 0:
        penalty = cfg.result_count_penalty * (result_count / _DEFAULT_TOTAL_GENES)
        base = max(base - penalty, 0.0)

    return base


def _compute_sensitivity(
    param_specs: list[ParameterSpec],
    study: optuna.Study | None = None,
) -> dict[str, float]:
    """Estimate per-parameter importance (0-1) using Optuna PED-ANOVA.

    Uses ``PedAnovaImportanceEvaluator`` -- a dependency-free evaluator
    shipped with Optuna that handles non-linear effects and parameter
    interactions.  Falls back to zeros when the study has too few completed
    trials (< 2).

    :param param_specs: Parameter specifications.
    :param study: Optuna study (default: None).
    :returns: Dict mapping parameter names to importance scores (0-1).
    """
    param_names = [p.name for p in param_specs]
    zeros = dict.fromkeys(param_names, 0.0)

    completed = (
        [t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE]
        if study is not None
        else []
    )
    if len(completed) < _MIN_COMPLETED_TRIALS:
        return zeros

    try:
        with warnings.catch_warnings():
            # Silence the "PedAnovaImportanceEvaluator is experimental" warning.
            warnings.filterwarnings("ignore", message="PedAnova")
            evaluator = optuna.importance.PedAnovaImportanceEvaluator()
            importances = optuna.importance.get_param_importances(
                study,
                evaluator=evaluator,
                params=param_names,
                normalize=True,
            )
        # Ensure every param is represented (evaluator may omit some).
        return {name: importances.get(name, 0.0) for name in param_names}
    except ValueError, TypeError, RuntimeError:
        logger.debug(
            "PED-ANOVA importance estimation failed, returning zeros",
            exc_info=True,
        )
        return zeros


def _compute_pareto_frontier(trials: list[TrialResult]) -> list[TrialResult]:
    """Two-objective Pareto: maximise recall, minimise FPR.

    :param trials: Trial results.
    :returns: Pareto frontier (non-dominated trials).
    """
    valid = [
        t for t in trials if t.recall is not None and t.false_positive_rate is not None
    ]
    if not valid:
        return []

    valid.sort(key=lambda t: t.recall or 0, reverse=True)
    frontier: list[TrialResult] = []
    best_fpr = float("inf")
    for t in valid:
        fpr = t.false_positive_rate or 0
        if fpr <= best_fpr:
            frontier.append(t)
            best_fpr = fpr
    return frontier


def _trial_to_json(trial: TrialResult) -> JSONObject:
    return {
        "trialNumber": trial.trial_number,
        "parameters": dict(trial.parameters),
        "score": round(trial.score, 4),
        "recall": round(trial.recall, 4) if trial.recall is not None else None,
        "falsePositiveRate": (
            round(trial.false_positive_rate, 4)
            if trial.false_positive_rate is not None
            else None
        ),
        "resultCount": trial.result_count,
        "positiveHits": trial.positive_hits,
        "negativeHits": trial.negative_hits,
        "totalPositives": trial.total_positives,
        "totalNegatives": trial.total_negatives,
    }


def result_to_json(result: OptimizationResult) -> JSONObject:
    return {
        "optimizationId": result.optimization_id,
        "status": result.status,
        "bestTrial": _trial_to_json(result.best_trial) if result.best_trial else None,
        "allTrials": [_trial_to_json(t) for t in result.all_trials],
        "paretoFrontier": [_trial_to_json(t) for t in result.pareto_frontier],
        "sensitivity": cast("JSONValue", result.sensitivity),
        "totalTimeSeconds": round(result.total_time_seconds, 2),
        "totalTrials": len(result.all_trials),
        "errorMessage": result.error_message,
    }
