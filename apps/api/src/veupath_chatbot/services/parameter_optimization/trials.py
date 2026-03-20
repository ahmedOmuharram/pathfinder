"""Trial execution loop for parameter optimization."""

import asyncio
import time
from dataclasses import dataclass
from enum import Enum

import optuna

from veupath_chatbot.platform.errors import AppError
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

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_CONSECUTIVE_FAILURES = 5
_PLATEAU_WINDOW = 10
_PERFECT_SCORE_THRESHOLD = 0.9999
_PARALLEL_CONCURRENCY = 4
_CACHE_PRECISION = 5


# ---------------------------------------------------------------------------
# Sampler creation
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Trial parameter suggestion
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Trial context (shared immutable config + mutable accumulated state)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# WDK metrics extraction
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TrialMetrics:
    """Intermediate metrics extracted from a WDK result."""

    recall: float | None
    fpr: float | None
    result_count: int | None
    positive_hits: int | None
    negative_hits: int | None


def _extract_trial_metrics(wdk_result: JSONObject) -> TrialMetrics:
    """Extract recall, FPR, result count, and hit counts from a WDK result."""
    target_data = wdk_result.get("target")
    pos_data = wdk_result.get("positive")
    neg_data = wdk_result.get("negative")

    recall_val = pos_data.get("recall") if isinstance(pos_data, dict) else None
    fpr_val = neg_data.get("falsePositiveRate") if isinstance(neg_data, dict) else None
    result_count_val = (
        target_data.get("resultCount") if isinstance(target_data, dict) else None
    )
    positive_hits_val = (
        pos_data.get("intersectionCount") if isinstance(pos_data, dict) else None
    )
    negative_hits_val = (
        neg_data.get("intersectionCount") if isinstance(neg_data, dict) else None
    )

    return TrialMetrics(
        recall=_to_float(recall_val),
        fpr=_to_float(fpr_val),
        result_count=_to_int(result_count_val),
        positive_hits=_to_int(positive_hits_val),
        negative_hits=_to_int(negative_hits_val),
    )


# ---------------------------------------------------------------------------
# Trial builders
# ---------------------------------------------------------------------------


def _build_failed_trial(
    *,
    trial_number: int,
    params: dict[str, JSONValue],
    n_positives: int,
    n_negatives: int,
) -> TrialResult:
    """Create a TrialResult for a trial that failed (WDK error or exception)."""
    return TrialResult(
        trial_number=trial_number,
        parameters=params,
        score=0.0,
        recall=None,
        false_positive_rate=None,
        result_count=None,
        total_positives=n_positives,
        total_negatives=n_negatives,
    )


def _build_successful_trial(
    *,
    trial_number: int,
    params: dict[str, JSONValue],
    wdk_result: JSONObject,
    cfg: OptimizationConfig,
    n_positives: int,
    n_negatives: int,
) -> TrialResult:
    """Create a TrialResult from a successful WDK evaluation."""
    metrics = _extract_trial_metrics(wdk_result)
    score = _compute_score(
        metrics.recall,
        metrics.fpr,
        cfg,
        result_count=metrics.result_count,
        positive_hits=metrics.positive_hits,
        negative_hits=metrics.negative_hits,
    )
    return TrialResult(
        trial_number=trial_number,
        parameters=params,
        score=score,
        recall=metrics.recall,
        false_positive_rate=metrics.fpr,
        result_count=metrics.result_count,
        positive_hits=metrics.positive_hits,
        negative_hits=metrics.negative_hits,
        total_positives=n_positives,
        total_negatives=n_negatives,
    )


# ---------------------------------------------------------------------------
# Result aggregation
# ---------------------------------------------------------------------------


def _aggregate_results(
    ctx: _TrialContext,
    status: str,
    error_message: str | None = None,
) -> OptimizationResult:
    """Build the final OptimizationResult from accumulated trial data."""
    elapsed = time.monotonic() - ctx.start_time
    return OptimizationResult(
        optimization_id=ctx.optimization_id,
        best_trial=ctx.best_trial,
        all_trials=ctx.trials,
        pareto_frontier=_compute_pareto_frontier(ctx.trials),
        sensitivity=_compute_sensitivity(ctx.parameter_space, ctx.study),
        total_time_seconds=elapsed,
        status=status,
        error_message=error_message,
    )


# ---------------------------------------------------------------------------
# Progress emission
# ---------------------------------------------------------------------------


async def _emit_trial_result(
    ctx: _TrialContext,
    *,
    trial_num: int,
    trial_result: TrialResult,
    wdk_error: str = "",
) -> None:
    """Emit a progress event for a single trial (failed or successful)."""
    if not ctx.progress_callback:
        return

    trial_json = _trial_to_json(trial_result)
    if wdk_error:
        trial_json = {**trial_json, "error": wdk_error}

    await emit_trial_progress(
        ctx.progress_callback,
        optimization_id=ctx.optimization_id,
        trial_num=trial_num,
        budget=ctx.budget,
        trial_json=trial_json,
        best_trial=ctx.best_trial,
        recent_trials=ctx.trials[-5:],
    )


# ---------------------------------------------------------------------------
# WDK evaluation (cached, semaphore-guarded)
# ---------------------------------------------------------------------------


def _cache_key(params: dict[str, JSONValue]) -> tuple[tuple[str, str], ...]:
    """Build a hashable key from optimised params (rounded floats)."""
    items: list[tuple[str, str]] = []
    for k in sorted(params):
        v = params[k]
        if isinstance(v, float):
            items.append((k, str(round(v, _CACHE_PRECISION))))
        else:
            items.append((k, str(v)))
    return tuple(items)


_EvalCache = dict[tuple[tuple[str, str], ...], tuple[JSONObject | None, str]]


async def _evaluate_trial(
    ctx: _TrialContext,
    trial_params: JSONObject,
    optimised_params: dict[str, JSONValue],
    sem: asyncio.Semaphore,
    cache: _EvalCache,
) -> tuple[JSONObject | None, str]:
    """Run WDK evaluation for a single trial (semaphore-guarded + cached).

    Returns (wdk_result_or_None, error_string).
    """
    key = _cache_key(optimised_params)
    cached = cache.get(key)
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
        except (AppError, ValueError, TypeError, KeyError) as trial_exc:
            wdk_error = str(trial_exc)
            wdk_result = None

        if wdk_result is not None and isinstance(wdk_result.get("error"), str):
            wdk_error = str(wdk_result["error"])
            wdk_result = None

        result_pair = (wdk_result, wdk_error)
        cache[key] = result_pair
        return result_pair


# ---------------------------------------------------------------------------
# Early-stop checks
# ---------------------------------------------------------------------------


class EarlyStopReason(Enum):
    """Why the optimisation loop stopped early."""

    PERFECT_SCORE = "perfect_score"
    PLATEAU = "plateau"


def _check_early_stop(
    *,
    best_trial: TrialResult | None,
    trials_since_improvement: int,
    plateau_window: int = _PLATEAU_WINDOW,
    perfect_score_threshold: float = _PERFECT_SCORE_THRESHOLD,
) -> EarlyStopReason | None:
    """Pure early-stop check (no side effects, no logging).

    Returns the reason for stopping, or None to continue.
    """
    if best_trial and best_trial.score >= perfect_score_threshold:
        return EarlyStopReason.PERFECT_SCORE
    if trials_since_improvement >= plateau_window:
        return EarlyStopReason.PLATEAU
    return None


def _should_early_stop(
    ctx: _TrialContext,
    trials_since_improvement: int,
    trial_num: int,
) -> bool:
    """Check whether the loop should stop early (with logging)."""
    reason = _check_early_stop(
        best_trial=ctx.best_trial,
        trials_since_improvement=trials_since_improvement,
    )
    if reason is None:
        return False

    match reason:
        case EarlyStopReason.PERFECT_SCORE:
            logger.info(
                "Early stop: perfect score reached",
                optimization_id=ctx.optimization_id,
                score=ctx.best_trial.score if ctx.best_trial else 0,
                trial=trial_num,
            )
        case EarlyStopReason.PLATEAU:
            logger.info(
                "Early stop: score plateau detected",
                optimization_id=ctx.optimization_id,
                best_score=ctx.best_trial.score if ctx.best_trial else 0,
                trials_without_improvement=trials_since_improvement,
                trial=trial_num,
            )
    return True


def _should_abort_on_failures(
    ctx: _TrialContext,
    consecutive_failures: int,
    wdk_error: str,
) -> str | None:
    """Return an error message if the loop should abort due to failures.

    Returns None if the loop should continue.
    """
    if consecutive_failures >= _MAX_CONSECUTIVE_FAILURES and ctx.best_trial is None:
        msg = (
            f"Aborted after {consecutive_failures} consecutive failures. "
            f"Last error: {wdk_error}"
        )
        logger.error(
            "Aborting optimisation: all trials failed",
            optimization_id=ctx.optimization_id,
            consecutive_failures=consecutive_failures,
            last_error=wdk_error,
        )
        return msg
    return None


# ---------------------------------------------------------------------------
# Single-trial processing
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _TrialOutcome:
    """Result of processing a single trial within the batch."""

    trial_result: TrialResult
    wdk_error: str
    grid_exhausted: bool
    is_failure: bool


def _unpack_gather_result(
    raw_result: tuple[JSONObject | None, str] | BaseException,
    trial_num: int,
    params: dict[str, JSONValue],
) -> tuple[JSONObject | None, str]:
    """Unpack a result from asyncio.gather (may be an exception)."""
    if isinstance(raw_result, BaseException):
        wdk_error = str(raw_result)
        logger.warning(
            "WDK evaluation failed for trial",
            trial=trial_num,
            params=params,
            error=wdk_error,
        )
        return None, wdk_error
    wdk_result, wdk_error = raw_result
    if wdk_error:
        logger.warning(
            "WDK evaluation failed for trial",
            trial=trial_num,
            params=params,
            error=wdk_error,
        )
    return wdk_result, wdk_error


def _process_single_trial(
    *,
    ctx: _TrialContext,
    ot: optuna.trial.Trial,
    params: dict[str, JSONValue],
    wdk_result: JSONObject | None,
    wdk_error: str,
    trial_num: int,
    n_positives: int,
    n_negatives: int,
) -> _TrialOutcome:
    """Process a single trial result: build TrialResult and report to Optuna."""
    if wdk_result is None:
        ctx.study.tell(ot, state=optuna.trial.TrialState.FAIL)
        return _TrialOutcome(
            trial_result=_build_failed_trial(
                trial_number=trial_num,
                params=params,
                n_positives=n_positives,
                n_negatives=n_negatives,
            ),
            wdk_error=wdk_error,
            grid_exhausted=False,
            is_failure=True,
        )

    trial_result = _build_successful_trial(
        trial_number=trial_num,
        params=params,
        wdk_result=wdk_result,
        cfg=ctx.cfg,
        n_positives=n_positives,
        n_negatives=n_negatives,
    )

    grid_exhausted = False
    try:
        ctx.study.tell(ot, trial_result.score)
    except RuntimeError as tell_exc:
        if "stop" in str(tell_exc).lower():
            logger.info(
                "Grid sampler exhausted search space",
                optimization_id=ctx.optimization_id,
                trial=trial_num,
            )
            grid_exhausted = True
        else:
            raise

    return _TrialOutcome(
        trial_result=trial_result,
        wdk_error=wdk_error,
        grid_exhausted=grid_exhausted,
        is_failure=False,
    )


# ---------------------------------------------------------------------------
# Batch processing
# ---------------------------------------------------------------------------


@dataclass
class _LoopState:
    """Mutable counters for the trial loop."""

    consecutive_failures: int = 0
    trials_since_improvement: int = 0
    abort_result: OptimizationResult | None = None


async def _handle_failed_outcome(
    ctx: _TrialContext,
    state: _LoopState,
    outcome: _TrialOutcome,
    trial_num: int,
) -> bool:
    """Handle a failed trial outcome. Returns True if the loop should abort."""
    state.consecutive_failures += 1
    await _emit_trial_result(
        ctx,
        trial_num=trial_num,
        trial_result=outcome.trial_result,
        wdk_error=outcome.wdk_error,
    )
    abort_msg = _should_abort_on_failures(
        ctx,
        state.consecutive_failures,
        outcome.wdk_error,
    )
    if abort_msg:
        if ctx.progress_callback:
            await emit_error(
                ctx.progress_callback,
                optimization_id=ctx.optimization_id,
                error=abort_msg,
            )
        state.abort_result = _aggregate_results(ctx, "error", abort_msg)
        return True
    return False


async def _handle_successful_outcome(
    ctx: _TrialContext,
    state: _LoopState,
    outcome: _TrialOutcome,
    trial_num: int,
) -> bool:
    """Handle a successful trial outcome. Returns True if the loop should stop."""
    state.consecutive_failures = 0
    if ctx.best_trial is None or outcome.trial_result.score > ctx.best_trial.score:
        ctx.best_trial = outcome.trial_result
        state.trials_since_improvement = 0
    else:
        state.trials_since_improvement += 1

    await _emit_trial_result(
        ctx,
        trial_num=trial_num,
        trial_result=outcome.trial_result,
    )
    return outcome.grid_exhausted or _should_early_stop(
        ctx,
        state.trials_since_improvement,
        trial_num,
    )


async def _process_batch(
    ctx: _TrialContext,
    state: _LoopState,
    optuna_trials: list[optuna.trial.Trial],
    batch_params: list[dict[str, JSONValue]],
    wdk_results: list[tuple[JSONObject | None, str] | BaseException],
    trial_idx: int,
    n_positives: int,
    n_negatives: int,
) -> bool:
    """Process all results in a batch. Returns True if the loop should stop."""
    for i, raw_result in enumerate(wdk_results):
        trial_num = trial_idx + i + 1
        wdk_result, wdk_error = _unpack_gather_result(
            raw_result,
            trial_num,
            batch_params[i],
        )
        outcome = _process_single_trial(
            ctx=ctx,
            ot=optuna_trials[i],
            params=batch_params[i],
            wdk_result=wdk_result,
            wdk_error=wdk_error,
            trial_num=trial_num,
            n_positives=n_positives,
            n_negatives=n_negatives,
        )
        ctx.trials.append(outcome.trial_result)

        if outcome.is_failure:
            if await _handle_failed_outcome(ctx, state, outcome, trial_num):
                return True
            continue

        if await _handle_successful_outcome(ctx, state, outcome, trial_num):
            return True

    return False


# ---------------------------------------------------------------------------
# Main trial loop
# ---------------------------------------------------------------------------


async def run_trial_loop(ctx: _TrialContext) -> OptimizationResult:
    """Execute the full trial loop and return an OptimizationResult."""
    n_positives = len(ctx.positive_controls or [])
    n_negatives = len(ctx.negative_controls or [])
    state = _LoopState()
    sem = asyncio.Semaphore(_PARALLEL_CONCURRENCY)
    eval_cache: _EvalCache = {}
    clean_fixed = {k: v for k, v in ctx.fixed_parameters.items() if v not in ("", None)}

    try:
        trial_idx = 0
        while trial_idx < ctx.budget:
            if ctx.check_cancelled and ctx.check_cancelled():
                logger.info(
                    "Optimization cancelled by user",
                    optimization_id=ctx.optimization_id,
                    completed_trials=len(ctx.trials),
                )
                break

            batch_size = min(_PARALLEL_CONCURRENCY, ctx.budget - trial_idx)
            optuna_trials = [ctx.study.ask() for _ in range(batch_size)]
            batch_params = [
                _suggest_trial_params(ot, ctx.parameter_space) for ot in optuna_trials
            ]

            full_params = [{**clean_fixed, **p} for p in batch_params]
            wdk_results = await asyncio.gather(
                *(
                    _evaluate_trial(ctx, fp, bp, sem, eval_cache)
                    for fp, bp in zip(full_params, batch_params, strict=False)
                ),
                return_exceptions=True,
            )

            should_stop = await _process_batch(
                ctx,
                state,
                optuna_trials,
                batch_params,
                wdk_results,
                trial_idx,
                n_positives,
                n_negatives,
            )
            if should_stop:
                if state.abort_result:
                    return state.abort_result
                break
            trial_idx += batch_size

    except (AppError, ValueError, TypeError, KeyError, RuntimeError) as exc:
        logger.error("Optimization failed", error=str(exc), exc_info=True)
        if ctx.progress_callback:
            await emit_error(
                ctx.progress_callback,
                optimization_id=ctx.optimization_id,
                error=str(exc),
            )
        return _aggregate_results(ctx, "error", str(exc))

    was_cancelled = ctx.check_cancelled() if ctx.check_cancelled else False
    status = "cancelled" if was_cancelled else "completed"
    return _aggregate_results(ctx, status)
