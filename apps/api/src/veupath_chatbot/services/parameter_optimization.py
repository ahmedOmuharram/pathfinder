"""Parameter optimization for VEuPathDB searches.

Optimizes search parameters against positive/negative control gene lists
using Bayesian optimization (TPE sampler via optuna), grid search, or random
search.  Each "trial" runs a temporary WDK strategy via
:func:`run_positive_negative_controls` and scores the result.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal, cast

import optuna

from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONArray, JSONObject, JSONValue
from veupath_chatbot.services.control_tests import (
    ControlValueFormat,
    run_positive_negative_controls,
)

logger = get_logger(__name__)

# Silence optuna's internal logging (we emit our own progress events).
optuna.logging.set_verbosity(optuna.logging.WARNING)

ProgressCallback = Callable[[JSONObject], Awaitable[None]]
"""Async callback that pushes an SSE event dict onto the agent event queue."""

CancelCheck = Callable[[], bool]
"""Returns True when the optimisation should stop early."""

OptimizationMethod = Literal["bayesian", "grid", "random"]
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
ParameterType = Literal["numeric", "integer", "categorical"]


@dataclass(frozen=True, slots=True)
class ParameterSpec:
    """Describes a single parameter to optimise."""

    name: str
    param_type: ParameterType
    # numeric / integer
    min_value: float | None = None
    max_value: float | None = None
    log_scale: bool = False
    step: float | None = None
    # categorical
    choices: list[str] | None = None


@dataclass(slots=True)
class OptimizationConfig:
    budget: int = 30
    objective: OptimizationObjective = "f1"
    beta: float = 1.0  # only for f_beta
    recall_weight: float = 1.0  # only for custom
    precision_weight: float = 1.0  # only for custom
    method: OptimizationMethod = "bayesian"
    result_count_penalty: float = 0.0
    """Weight for penalising large result sets.  The penalty is
    ``result_count_penalty * (result_count / total_genes)`` where
    *total_genes* is the denominator (defaults to 20 000 if unknown).
    A small value (e.g. 0.1) acts as a tiebreaker; higher values make
    the optimiser strongly prefer tighter results."""


@dataclass(frozen=True, slots=True)
class TrialResult:
    trial_number: int
    parameters: dict[str, JSONValue]
    score: float
    recall: float | None
    false_positive_rate: float | None
    result_count: int | None
    positive_hits: int | None = None
    negative_hits: int | None = None
    total_positives: int | None = None
    total_negatives: int | None = None


@dataclass(slots=True)
class OptimizationResult:
    optimization_id: str
    best_trial: TrialResult | None
    all_trials: list[TrialResult]
    pareto_frontier: list[TrialResult]
    sensitivity: dict[str, float]
    total_time_seconds: float
    status: str  # completed | cancelled | error
    error_message: str | None = None


_DEFAULT_TOTAL_GENES = 20_000
"""Fallback denominator when the total gene count is unknown."""


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


def _compute_score(
    recall: float | None,
    fpr: float | None,
    cfg: OptimizationConfig,
    *,
    result_count: int | None = None,
) -> float:
    r = recall if recall is not None else 0.0
    raw_fpr = fpr if fpr is not None else 0.0
    precision = 1.0 - raw_fpr
    specificity = 1.0 - raw_fpr

    match cfg.objective:
        case "recall":
            base = r
        case "precision":
            base = precision
        case "specificity":
            base = specificity
        case "balanced_accuracy":
            base = (r + specificity) / 2.0
        case "mcc":
            # Approximation from recall and specificity when only aggregate rates
            # are available: MCC = (TPR*TNR - FPR*FNR) / sqrt((TPR+FPR)*(TPR+FNR)*(TNR+FPR)*(TNR+FNR))
            tpr, tnr, fpr_val, fnr = r, specificity, raw_fpr, 1.0 - r
            num = tpr * tnr - fpr_val * fnr
            denom = (
                (tpr + fpr_val) * (tpr + fnr) * (tnr + fpr_val) * (tnr + fnr)
            ) ** 0.5
            base = (num / denom) if denom > 1e-10 else 0.0
        case "youdens_j":
            base = r + specificity - 1.0
        case "f1":
            denom = precision + r
            base = (2 * precision * r / denom) if denom > 0 else 0.0
        case "f_beta":
            b2 = cfg.beta**2
            denom = b2 * precision + r
            base = ((1 + b2) * precision * r / denom) if denom > 0 else 0.0
        case "custom":
            base = cfg.recall_weight * r - cfg.precision_weight * raw_fpr
        case _:
            base = r

    # Apply optional result-count penalty (tiebreaker for large result sets).
    if cfg.result_count_penalty > 0 and result_count is not None and result_count > 0:
        penalty = cfg.result_count_penalty * (result_count / _DEFAULT_TOTAL_GENES)
        base = max(base - penalty, 0.0)

    return base


def _compute_sensitivity(
    param_specs: list[ParameterSpec],
    study: optuna.Study | None = None,
) -> dict[str, float]:
    """Estimate per-parameter importance (0–1) using Optuna PED-ANOVA.

    Uses ``PedAnovaImportanceEvaluator`` — a dependency-free evaluator
    shipped with Optuna that handles non-linear effects and parameter
    interactions.  Falls back to zeros when the study has too few completed
    trials (< 2).

    :param param_specs: Parameter specifications.
    :param study: Optuna study (default: None).
    :returns: Dict mapping parameter names to importance scores (0–1).
    """
    param_names = [p.name for p in param_specs]
    zeros = dict.fromkeys(param_names, 0.0)

    if study is None:
        return zeros

    completed = [t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE]
    if len(completed) < 2:
        return zeros

    try:
        import warnings

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
    except Exception:
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
        "sensitivity": cast(JSONValue, result.sensitivity),
        "totalTimeSeconds": round(result.total_time_seconds, 2),
        "totalTrials": len(result.all_trials),
        "errorMessage": result.error_message,
    }


async def optimize_search_parameters(
    *,
    site_id: str,
    record_type: str,
    search_name: str,
    fixed_parameters: dict[str, JSONValue],
    parameter_space: list[ParameterSpec],
    controls_search_name: str,
    controls_param_name: str,
    positive_controls: list[str] | None = None,
    negative_controls: list[str] | None = None,
    controls_value_format: ControlValueFormat = "newline",
    controls_extra_parameters: JSONObject | None = None,
    id_field: str | None = None,
    config: OptimizationConfig | None = None,
    progress_callback: ProgressCallback | None = None,
    check_cancelled: CancelCheck | None = None,
) -> OptimizationResult:
    """Run parameter optimisation against positive/negative controls.

    Returns an :class:`OptimizationResult` with the best configuration,
    all trials, Pareto frontier, and sensitivity analysis.
    """
    cfg = config or OptimizationConfig()
    optimization_id = f"opt_{int(time.time() * 1000)}"
    trials: list[TrialResult] = []
    best_trial: TrialResult | None = None
    start_time = time.monotonic()
    budget = cfg.budget

    param_space_json: JSONArray = [
        {
            "name": p.name,
            "type": p.param_type,
            "minValue": p.min_value,
            "maxValue": p.max_value,
            "logScale": p.log_scale,
            "choices": cast(JSONValue, p.choices),
        }
        for p in parameter_space
    ]

    if progress_callback:
        await progress_callback(
            {
                "type": "optimization_progress",
                "data": {
                    "optimizationId": optimization_id,
                    "status": "started",
                    "searchName": search_name,
                    "recordType": record_type,
                    "budget": budget,
                    "objective": cfg.objective,
                    "positiveControlsCount": len(positive_controls or []),
                    "negativeControlsCount": len(negative_controls or []),
                    "parameterSpace": param_space_json,
                    "currentTrial": 0,
                    "totalTrials": budget,
                    "bestTrial": None,
                    "recentTrials": [],
                },
            }
        )

    sampler: optuna.samplers.BaseSampler
    match cfg.method:
        case "bayesian":
            sampler = optuna.samplers.TPESampler(seed=42)
        case "grid":
            # Build grid search space from param specs.
            grid: dict[str, list[float | int | str]] = {}
            for p in parameter_space:
                if p.param_type == "categorical" and p.choices:
                    grid[p.name] = list(p.choices)
                elif p.param_type == "integer":
                    lo, hi = int(p.min_value or 0), int(p.max_value or 10)
                    st = int(p.step) if p.step else max(1, (hi - lo) // 10)
                    grid[p.name] = list(range(lo, hi + 1, st))
                else:  # numeric
                    lo_f, hi_f = p.min_value or 0.0, p.max_value or 1.0
                    n_levels = min(10, budget)
                    step_size = (hi_f - lo_f) / max(n_levels - 1, 1)
                    grid[p.name] = [lo_f + i * step_size for i in range(n_levels)]
            sampler = optuna.samplers.GridSampler(grid)
            # Grid search may have fewer combos than requested budget
            total_combos: int = 1
            for v in grid.values():
                total_combos *= len(v)
            budget = int(min(total_combos, budget))
        case "random":
            sampler = optuna.samplers.RandomSampler(seed=42)
        case _:
            sampler = optuna.samplers.TPESampler(seed=42)

    study = optuna.create_study(direction="maximize", sampler=sampler)

    n_positives = len(positive_controls or [])
    n_negatives = len(negative_controls or [])

    # Early-abort: stop if the first N consecutive trials all fail (same fixed
    # params → same error every time, pointless to keep going).
    max_consecutive_failures_limit = 5
    consecutive_failures = 0

    # Convergence-based early stopping.
    plateau_window = 10  # stop if best score hasn't improved in this many trials
    perfect_score_threshold = 0.9999  # close enough to 1.0 to call it perfect
    trials_since_improvement = 0

    # Parallel execution with a semaphore to limit WDK concurrency.
    parallel_concurrency = 4
    sem = asyncio.Semaphore(parallel_concurrency)

    # Parameter deduplication cache.  Avoids redundant WDK calls when
    # Optuna suggests very similar (or identical) parameters.
    cache_precision = 5  # round floats to this many decimals
    _eval_cache: dict[
        tuple[tuple[str, str], ...],
        tuple[JSONObject | None, str],
    ] = {}

    def _cache_key(params: dict[str, JSONValue]) -> tuple[tuple[str, str], ...]:
        """Build a hashable key from optimised params (rounded floats).

        :param params: Optimised parameter dict.
        :returns: Hashable key for caching.
        """
        items: list[tuple[str, str]] = []
        for k in sorted(params):
            v = params[k]
            if isinstance(v, float):
                items.append((k, str(round(v, cache_precision))))
            else:
                items.append((k, str(v)))
        return tuple(items)

    async def _evaluate_trial(
        trial_params: JSONObject,
        optimised_params: dict[str, JSONValue],
    ) -> tuple[JSONObject | None, str]:
        """Run WDK evaluation for a single trial (semaphore-guarded + cached).

        Returns (wdk_result_or_None, error_string).
        """
        key = _cache_key(optimised_params)
        cached = _eval_cache.get(key)
        if cached is not None:
            logger.debug("Cache hit for params", key=key)
            return cached

        async with sem:
            wdk_error = ""
            wdk_result: JSONObject | None = None
            try:
                wdk_result = await run_positive_negative_controls(
                    site_id=site_id,
                    record_type=record_type,
                    target_search_name=search_name,
                    target_parameters=trial_params,
                    controls_search_name=controls_search_name,
                    controls_param_name=controls_param_name,
                    positive_controls=positive_controls,
                    negative_controls=negative_controls,
                    controls_value_format=controls_value_format,
                    controls_extra_parameters=controls_extra_parameters,
                    id_field=id_field,
                )
            except Exception as trial_exc:
                wdk_error = str(trial_exc)
                wdk_result = None

            if wdk_result is not None and isinstance(wdk_result.get("error"), str):
                wdk_error = str(wdk_result["error"])
                wdk_result = None

            result_pair = (wdk_result, wdk_error)
            _eval_cache[key] = result_pair
            return result_pair

    try:
        trial_idx = 0
        stop_loop = False
        while trial_idx < budget and not stop_loop:
            if check_cancelled and check_cancelled():
                logger.info(
                    "Optimization cancelled by user",
                    optimization_id=optimization_id,
                    completed_trials=len(trials),
                )
                break

            batch_size = min(parallel_concurrency, budget - trial_idx)
            optuna_trials: list[optuna.trial.Trial] = []
            batch_params: list[dict[str, JSONValue]] = []
            for _ in range(batch_size):
                ot = study.ask()
                params: dict[str, JSONValue] = {}
                for spec in parameter_space:
                    if spec.param_type == "numeric":
                        params[spec.name] = ot.suggest_float(
                            spec.name,
                            spec.min_value or 0.0,
                            spec.max_value or 1.0,
                            log=spec.log_scale,
                        )
                    elif spec.param_type == "integer":
                        params[spec.name] = ot.suggest_int(
                            spec.name,
                            int(spec.min_value or 0),
                            int(spec.max_value or 100),
                            step=int(spec.step) if spec.step else 1,
                        )
                    elif spec.param_type == "categorical":
                        params[spec.name] = ot.suggest_categorical(
                            spec.name,
                            spec.choices or [""],
                        )
                optuna_trials.append(ot)
                batch_params.append(params)

            full_params_list = [{**fixed_parameters, **p} for p in batch_params]
            wdk_results = await asyncio.gather(
                *(
                    _evaluate_trial(fp, bp)
                    for fp, bp in zip(full_params_list, batch_params, strict=False)
                ),
                return_exceptions=True,
            )

            for i, raw_result in enumerate(wdk_results):
                trial_num = trial_idx + i
                ot = optuna_trials[i]
                params = batch_params[i]

                # Handle unexpected exceptions from gather.
                if isinstance(raw_result, BaseException):
                    wdk_result: JSONObject | None = None
                    wdk_error = str(raw_result)
                    logger.warning(
                        "WDK evaluation failed for trial",
                        trial=trial_num + 1,
                        params=params,
                        error=wdk_error,
                    )
                else:
                    wdk_result, wdk_error = raw_result

                if wdk_error:
                    logger.warning(
                        "WDK evaluation failed for trial",
                        trial=trial_num + 1,
                        params=params,
                        error=wdk_error,
                    )

                # Handle failed trials (exception or error dict).
                if wdk_result is None:
                    study.tell(ot, state=optuna.trial.TrialState.FAIL)
                    failed_trial = TrialResult(
                        trial_number=trial_num + 1,
                        parameters=params,
                        score=0.0,
                        recall=None,
                        false_positive_rate=None,
                        result_count=None,
                        total_positives=n_positives,
                        total_negatives=n_negatives,
                    )
                    trials.append(failed_trial)
                    consecutive_failures += 1
                    if progress_callback:
                        await progress_callback(
                            {
                                "type": "optimization_progress",
                                "data": {
                                    "optimizationId": optimization_id,
                                    "status": "running",
                                    "currentTrial": trial_num + 1,
                                    "totalTrials": budget,
                                    "trial": {
                                        **_trial_to_json(failed_trial),
                                        "error": wdk_error,
                                    },
                                    "bestTrial": (
                                        _trial_to_json(best_trial)
                                        if best_trial
                                        else None
                                    ),
                                    "recentTrials": [
                                        _trial_to_json(t) for t in trials[-5:]
                                    ],
                                },
                            }
                        )

                    # Early abort: if ALL trials so far have failed, the fixed
                    # parameters are likely invalid and every subsequent trial
                    # will fail identically.
                    if (
                        consecutive_failures >= max_consecutive_failures_limit
                        and best_trial is None
                    ):
                        logger.error(
                            "Aborting optimisation: all trials failed",
                            optimization_id=optimization_id,
                            consecutive_failures=consecutive_failures,
                            last_error=wdk_error,
                        )
                        elapsed = time.monotonic() - start_time
                        error_msg = (
                            f"Aborted after {consecutive_failures} consecutive failures. "
                            f"Last error: {wdk_error}"
                        )
                        if progress_callback:
                            await progress_callback(
                                {
                                    "type": "optimization_progress",
                                    "data": {
                                        "optimizationId": optimization_id,
                                        "status": "error",
                                        "error": error_msg,
                                    },
                                }
                            )
                        return OptimizationResult(
                            optimization_id=optimization_id,
                            best_trial=None,
                            all_trials=trials,
                            pareto_frontier=[],
                            sensitivity=_compute_sensitivity(parameter_space, study),
                            total_time_seconds=elapsed,
                            status="error",
                            error_message=error_msg,
                        )
                    continue

                consecutive_failures = 0

                target_data = wdk_result.get("target")
                pos_data = wdk_result.get("positive")
                neg_data = wdk_result.get("negative")

                recall_val = (
                    pos_data.get("recall") if isinstance(pos_data, dict) else None
                )
                fpr_val = (
                    neg_data.get("falsePositiveRate")
                    if isinstance(neg_data, dict)
                    else None
                )
                result_count_val = (
                    target_data.get("resultCount")
                    if isinstance(target_data, dict)
                    else None
                )
                positive_hits_val = (
                    pos_data.get("intersectionCount")
                    if isinstance(pos_data, dict)
                    else None
                )
                negative_hits_val = (
                    neg_data.get("intersectionCount")
                    if isinstance(neg_data, dict)
                    else None
                )
                recall = _to_float(recall_val)
                fpr = _to_float(fpr_val)
                result_count = _to_int(result_count_val)
                positive_hits = _to_int(positive_hits_val)
                negative_hits = _to_int(negative_hits_val)

                score = _compute_score(recall, fpr, cfg, result_count=result_count)

                grid_exhausted = False
                try:
                    study.tell(ot, score)
                except RuntimeError as tell_exc:
                    if "stop" in str(tell_exc).lower():
                        logger.info(
                            "Grid sampler exhausted search space",
                            optimization_id=optimization_id,
                            trial=trial_num + 1,
                        )
                        grid_exhausted = True
                    else:
                        raise

                trial_result = TrialResult(
                    trial_number=trial_num + 1,
                    parameters=params,
                    score=score,
                    recall=recall,
                    false_positive_rate=fpr,
                    result_count=result_count,
                    positive_hits=positive_hits,
                    negative_hits=negative_hits,
                    total_positives=n_positives,
                    total_negatives=n_negatives,
                )
                trials.append(trial_result)

                if best_trial is None or score > best_trial.score:
                    best_trial = trial_result
                    trials_since_improvement = 0
                else:
                    trials_since_improvement += 1

                if progress_callback:
                    await progress_callback(
                        {
                            "type": "optimization_progress",
                            "data": {
                                "optimizationId": optimization_id,
                                "status": "running",
                                "currentTrial": trial_num + 1,
                                "totalTrials": budget,
                                "trial": _trial_to_json(trial_result),
                                "bestTrial": (
                                    _trial_to_json(best_trial) if best_trial else None
                                ),
                                "recentTrials": [
                                    _trial_to_json(t) for t in trials[-5:]
                                ],
                            },
                        }
                    )

                if grid_exhausted:
                    stop_loop = True
                    break

                if best_trial and best_trial.score >= perfect_score_threshold:
                    logger.info(
                        "Early stop: perfect score reached",
                        optimization_id=optimization_id,
                        score=best_trial.score,
                        trial=trial_num + 1,
                    )
                    stop_loop = True
                    break

                if trials_since_improvement >= plateau_window:
                    logger.info(
                        "Early stop: score plateau detected",
                        optimization_id=optimization_id,
                        best_score=best_trial.score if best_trial else 0,
                        trials_without_improvement=trials_since_improvement,
                        trial=trial_num + 1,
                    )
                    stop_loop = True
                    break

            trial_idx += batch_size

    except Exception as exc:
        logger.error("Optimization failed", error=str(exc), exc_info=True)
        elapsed = time.monotonic() - start_time
        if progress_callback:
            await progress_callback(
                {
                    "type": "optimization_progress",
                    "data": {
                        "optimizationId": optimization_id,
                        "status": "error",
                        "error": str(exc),
                    },
                }
            )
        return OptimizationResult(
            optimization_id=optimization_id,
            best_trial=best_trial,
            all_trials=trials,
            pareto_frontier=_compute_pareto_frontier(trials),
            sensitivity=_compute_sensitivity(parameter_space, study),
            total_time_seconds=elapsed,
            status="error",
            error_message=str(exc),
        )

    was_cancelled = check_cancelled() if check_cancelled else False
    status = "cancelled" if was_cancelled else "completed"
    elapsed = time.monotonic() - start_time
    pareto = _compute_pareto_frontier(trials)
    sensitivity = _compute_sensitivity(parameter_space, study)

    if progress_callback:
        await progress_callback(
            {
                "type": "optimization_progress",
                "data": {
                    "optimizationId": optimization_id,
                    "status": status,
                    "currentTrial": len(trials),
                    "totalTrials": budget,
                    "bestTrial": _trial_to_json(best_trial) if best_trial else None,
                    "allTrials": [_trial_to_json(t) for t in trials],
                    "paretoFrontier": [_trial_to_json(t) for t in pareto],
                    "sensitivity": cast(JSONValue, sensitivity),
                    "totalTimeSeconds": round(elapsed, 2),
                },
            }
        )

    return OptimizationResult(
        optimization_id=optimization_id,
        best_trial=best_trial,
        all_trials=trials,
        pareto_frontier=pareto,
        sensitivity=sensitivity,
        total_time_seconds=elapsed,
        status=status,
    )
