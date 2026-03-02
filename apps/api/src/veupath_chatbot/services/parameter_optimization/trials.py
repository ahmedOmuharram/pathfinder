"""Trial execution loop for parameter optimization."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

import optuna

from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject, JSONValue
from veupath_chatbot.services.control_tests import run_positive_negative_controls
from veupath_chatbot.services.experiment.types import ControlValueFormat
from veupath_chatbot.services.parameter_optimization.callbacks import (
    emit_error,
    emit_trial_progress,
)
from veupath_chatbot.services.parameter_optimization.config import (
    CancelCheck,
    OptimizationConfig,
    OptimizationResult,
    ParameterSpec,
    ProgressCallback,
    TrialResult,
)
from veupath_chatbot.services.parameter_optimization.scoring import (
    _compute_pareto_frontier,
    _compute_score,
    _compute_sensitivity,
    _to_float,
    _to_int,
    _trial_to_json,
)

logger = get_logger(__name__)


def _create_sampler(
    cfg: OptimizationConfig,
    parameter_space: list[ParameterSpec],
    budget: int,
) -> tuple[optuna.samplers.BaseSampler, int]:
    """Create an Optuna sampler and (possibly adjusted) budget.

    Grid search may reduce *budget* if the total number of combinations
    is smaller than the requested budget.
    """
    match cfg.method:
        case "bayesian":
            return optuna.samplers.TPESampler(seed=42), budget
        case "grid":
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
            total_combos: int = 1
            for v in grid.values():
                total_combos *= len(v)
            return optuna.samplers.GridSampler(grid), int(min(total_combos, budget))
        case "random":
            return optuna.samplers.RandomSampler(seed=42), budget
        case _:
            return optuna.samplers.TPESampler(seed=42), budget


def _suggest_trial_params(
    trial: optuna.trial.Trial,
    parameter_space: list[ParameterSpec],
) -> dict[str, JSONValue]:
    """Suggest parameter values for one Optuna trial."""
    params: dict[str, JSONValue] = {}
    for spec in parameter_space:
        if spec.param_type == "numeric":
            params[spec.name] = trial.suggest_float(
                spec.name,
                spec.min_value or 0.0,
                spec.max_value or 1.0,
                log=spec.log_scale,
            )
        elif spec.param_type == "integer":
            params[spec.name] = trial.suggest_int(
                spec.name,
                int(spec.min_value or 0),
                int(spec.max_value or 100),
                step=int(spec.step) if spec.step else 1,
            )
        elif spec.param_type == "categorical":
            params[spec.name] = trial.suggest_categorical(
                spec.name,
                spec.choices or [""],
            )
    return params


@dataclass
class _TrialContext:
    """Mutable state shared across the trial loop."""

    site_id: str
    record_type: str
    search_name: str
    fixed_parameters: dict[str, JSONValue]
    parameter_space: list[ParameterSpec]
    controls_search_name: str
    controls_param_name: str
    positive_controls: list[str] | None
    negative_controls: list[str] | None
    controls_value_format: ControlValueFormat
    controls_extra_parameters: JSONObject | None
    id_field: str | None
    cfg: OptimizationConfig
    optimization_id: str
    budget: int
    study: optuna.Study
    progress_callback: ProgressCallback | None
    check_cancelled: CancelCheck | None
    start_time: float

    # Accumulated state
    trials: list[TrialResult]
    best_trial: TrialResult | None = None


async def run_trial_loop(ctx: _TrialContext) -> OptimizationResult:
    """Execute the full trial loop and return an OptimizationResult."""
    n_positives = len(ctx.positive_controls or [])
    n_negatives = len(ctx.negative_controls or [])

    max_consecutive_failures_limit = 5
    consecutive_failures = 0

    plateau_window = 10
    perfect_score_threshold = 0.9999
    trials_since_improvement = 0

    parallel_concurrency = 4
    sem = asyncio.Semaphore(parallel_concurrency)

    cache_precision = 5
    _eval_cache: dict[
        tuple[tuple[str, str], ...],
        tuple[JSONObject | None, str],
    ] = {}

    def _cache_key(params: dict[str, JSONValue]) -> tuple[tuple[str, str], ...]:
        """Build a hashable key from optimised params (rounded floats)."""
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
                    site_id=ctx.site_id,
                    record_type=ctx.record_type,
                    target_search_name=ctx.search_name,
                    target_parameters=trial_params,
                    controls_search_name=ctx.controls_search_name,
                    controls_param_name=ctx.controls_param_name,
                    positive_controls=ctx.positive_controls,
                    negative_controls=ctx.negative_controls,
                    controls_value_format=ctx.controls_value_format,
                    controls_extra_parameters=ctx.controls_extra_parameters,
                    id_field=ctx.id_field,
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
        while trial_idx < ctx.budget and not stop_loop:
            if ctx.check_cancelled and ctx.check_cancelled():
                logger.info(
                    "Optimization cancelled by user",
                    optimization_id=ctx.optimization_id,
                    completed_trials=len(ctx.trials),
                )
                break

            batch_size = min(parallel_concurrency, ctx.budget - trial_idx)
            optuna_trials: list[optuna.trial.Trial] = []
            batch_params: list[dict[str, JSONValue]] = []
            for _ in range(batch_size):
                ot = ctx.study.ask()
                params = _suggest_trial_params(ot, ctx.parameter_space)
                optuna_trials.append(ot)
                batch_params.append(params)

            clean_fixed = {
                k: v for k, v in ctx.fixed_parameters.items() if v not in ("", None)
            }
            full_params_list = [{**clean_fixed, **p} for p in batch_params]
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
                    ctx.study.tell(ot, state=optuna.trial.TrialState.FAIL)
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
                    ctx.trials.append(failed_trial)
                    consecutive_failures += 1
                    if ctx.progress_callback:
                        await emit_trial_progress(
                            ctx.progress_callback,
                            optimization_id=ctx.optimization_id,
                            trial_num=trial_num + 1,
                            budget=ctx.budget,
                            trial_json={
                                **_trial_to_json(failed_trial),
                                "error": wdk_error,
                            },
                            best_trial=ctx.best_trial,
                            recent_trials=ctx.trials[-5:],
                        )

                    # Early abort: if ALL trials so far have failed, the fixed
                    # parameters are likely invalid and every subsequent trial
                    # will fail identically.
                    if (
                        consecutive_failures >= max_consecutive_failures_limit
                        and ctx.best_trial is None
                    ):
                        logger.error(
                            "Aborting optimisation: all trials failed",
                            optimization_id=ctx.optimization_id,
                            consecutive_failures=consecutive_failures,
                            last_error=wdk_error,
                        )
                        elapsed = time.monotonic() - ctx.start_time
                        error_msg = (
                            f"Aborted after {consecutive_failures} consecutive failures. "
                            f"Last error: {wdk_error}"
                        )
                        if ctx.progress_callback:
                            await emit_error(
                                ctx.progress_callback,
                                optimization_id=ctx.optimization_id,
                                error=error_msg,
                            )
                        return OptimizationResult(
                            optimization_id=ctx.optimization_id,
                            best_trial=None,
                            all_trials=ctx.trials,
                            pareto_frontier=[],
                            sensitivity=_compute_sensitivity(
                                ctx.parameter_space, ctx.study
                            ),
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

                score = _compute_score(
                    recall,
                    fpr,
                    ctx.cfg,
                    result_count=result_count,
                    positive_hits=positive_hits,
                    negative_hits=negative_hits,
                )

                grid_exhausted = False
                try:
                    ctx.study.tell(ot, score)
                except RuntimeError as tell_exc:
                    if "stop" in str(tell_exc).lower():
                        logger.info(
                            "Grid sampler exhausted search space",
                            optimization_id=ctx.optimization_id,
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
                ctx.trials.append(trial_result)

                if ctx.best_trial is None or score > ctx.best_trial.score:
                    ctx.best_trial = trial_result
                    trials_since_improvement = 0
                else:
                    trials_since_improvement += 1

                if ctx.progress_callback:
                    await emit_trial_progress(
                        ctx.progress_callback,
                        optimization_id=ctx.optimization_id,
                        trial_num=trial_num + 1,
                        budget=ctx.budget,
                        trial_json=_trial_to_json(trial_result),
                        best_trial=ctx.best_trial,
                        recent_trials=ctx.trials[-5:],
                    )

                if grid_exhausted:
                    stop_loop = True
                    break

                if ctx.best_trial and ctx.best_trial.score >= perfect_score_threshold:
                    logger.info(
                        "Early stop: perfect score reached",
                        optimization_id=ctx.optimization_id,
                        score=ctx.best_trial.score,
                        trial=trial_num + 1,
                    )
                    stop_loop = True
                    break

                if trials_since_improvement >= plateau_window:
                    logger.info(
                        "Early stop: score plateau detected",
                        optimization_id=ctx.optimization_id,
                        best_score=ctx.best_trial.score if ctx.best_trial else 0,
                        trials_without_improvement=trials_since_improvement,
                        trial=trial_num + 1,
                    )
                    stop_loop = True
                    break

            trial_idx += batch_size

    except Exception as exc:
        logger.error("Optimization failed", error=str(exc), exc_info=True)
        elapsed = time.monotonic() - ctx.start_time
        if ctx.progress_callback:
            await emit_error(
                ctx.progress_callback,
                optimization_id=ctx.optimization_id,
                error=str(exc),
            )
        return OptimizationResult(
            optimization_id=ctx.optimization_id,
            best_trial=ctx.best_trial,
            all_trials=ctx.trials,
            pareto_frontier=_compute_pareto_frontier(ctx.trials),
            sensitivity=_compute_sensitivity(ctx.parameter_space, ctx.study),
            total_time_seconds=elapsed,
            status="error",
            error_message=str(exc),
        )

    was_cancelled = ctx.check_cancelled() if ctx.check_cancelled else False
    status = "cancelled" if was_cancelled else "completed"
    elapsed = time.monotonic() - ctx.start_time
    pareto = _compute_pareto_frontier(ctx.trials)
    sensitivity = _compute_sensitivity(ctx.parameter_space, ctx.study)

    return OptimizationResult(
        optimization_id=ctx.optimization_id,
        best_trial=ctx.best_trial,
        all_trials=ctx.trials,
        pareto_frontier=pareto,
        sensitivity=sensitivity,
        total_time_seconds=elapsed,
        status=status,
    )
