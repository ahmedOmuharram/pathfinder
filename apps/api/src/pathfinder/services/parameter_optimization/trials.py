"""Trial execution loop for parameter optimization."""

import asyncio

from pathfinder.platform.errors import AppError
from pathfinder.platform.logging import get_logger
from pathfinder.services.parameter_optimization.batch import (
    BatchInput,
    LoopState,
    TrialContext,
    aggregate_results,
    process_batch,
)
from pathfinder.services.parameter_optimization.callbacks import (
    emit_error,
)
from pathfinder.services.parameter_optimization.config import (
    OptimizationResult,
)
from pathfinder.services.parameter_optimization.evaluation import (
    _PARALLEL_CONCURRENCY,
    EvalRequest,
    _EvalCache,
    _evaluate_trial,
    _KeyLocks,
)
from pathfinder.services.parameter_optimization.sampler import (
    _suggest_trial_params,
)

logger = get_logger(__name__)


async def run_trial_loop(ctx: TrialContext) -> OptimizationResult:
    """Execute the full trial loop and return an OptimizationResult."""
    n_positives = len(ctx.inp.positive_controls or [])
    n_negatives = len(ctx.inp.negative_controls or [])
    state = LoopState()
    sem = asyncio.Semaphore(_PARALLEL_CONCURRENCY)
    eval_cache: _EvalCache = {}
    eval_key_locks: _KeyLocks = {}
    clean_fixed = {
        k: v for k, v in ctx.inp.fixed_parameters.items() if v not in ("", None)
    }

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
                _suggest_trial_params(ot, ctx.inp.parameter_space)
                for ot in optuna_trials
            ]

            full_params = [{**clean_fixed, **p} for p in batch_params]
            requests = [
                EvalRequest(
                    config=ctx.build_intersection_config(fp),
                    positive_controls=ctx.inp.positive_controls,
                    negative_controls=ctx.inp.negative_controls,
                )
                for fp in full_params
            ]
            wdk_results = await asyncio.gather(
                *(
                    _evaluate_trial(req, bp, sem, eval_cache, eval_key_locks)
                    for req, bp in zip(requests, batch_params, strict=False)
                ),
                return_exceptions=True,
            )

            should_stop = await process_batch(
                ctx,
                state,
                BatchInput(
                    optuna_trials=optuna_trials,
                    batch_params=batch_params,
                    wdk_results=wdk_results,
                    trial_idx=trial_idx,
                    n_positives=n_positives,
                    n_negatives=n_negatives,
                ),
            )
            if should_stop:
                if state.abort_result:
                    return state.abort_result
                break
            trial_idx += batch_size

    except (AppError, RuntimeError) as exc:
        logger.error("Optimization failed", error=str(exc), exc_info=True)
        if ctx.progress_callback:
            await emit_error(
                ctx.progress_callback,
                optimization_id=ctx.optimization_id,
                error=str(exc),
            )
        return aggregate_results(ctx, "error", str(exc))

    was_cancelled = ctx.check_cancelled() if ctx.check_cancelled else False
    status = "cancelled" if was_cancelled else "completed"
    return aggregate_results(ctx, status)
