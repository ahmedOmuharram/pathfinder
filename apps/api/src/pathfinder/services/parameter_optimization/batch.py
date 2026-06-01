"""Batch processing for parameter optimization trials."""

import time
from dataclasses import dataclass

import optuna

from pathfinder.domain.parameters.values import ParamValue
from pathfinder.platform.logging import get_logger
from pathfinder.services.control_tests import IntersectionConfig
from pathfinder.services.experiment.types import ControlTestResult
from pathfinder.services.parameter_optimization.builders import (
    _build_failed_trial,
    _build_successful_trial,
)
from pathfinder.services.parameter_optimization.callbacks import (
    TrialProgressEvent,
    emit_error,
    emit_trial_progress,
)
from pathfinder.services.parameter_optimization.config import (
    CancelCheck,
    OptimizationConfig,
    OptimizationInput,
    OptimizationResult,
    ProgressCallback,
    TrialResult,
)
from pathfinder.services.parameter_optimization.early_stop import (
    _should_abort_on_failures,
    _should_early_stop,
)
from pathfinder.services.parameter_optimization.evaluation import (
    _unpack_gather_result,
)
from pathfinder.services.parameter_optimization.scoring import (
    _compute_pareto_frontier,
    _compute_sensitivity,
)

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Trial context (shared immutable config + mutable accumulated state)
# ---------------------------------------------------------------------------


@dataclass
class TrialContext:
    """Mutable state shared across the trial loop."""

    inp: OptimizationInput
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

    def build_intersection_config(
        self,
        target_parameters: dict[str, ParamValue],
    ) -> IntersectionConfig:
        """Build an :class:`IntersectionConfig` for a trial evaluation."""
        return IntersectionConfig(
            site_id=self.inp.site_id,
            record_type=self.inp.record_type,
            target_search_name=self.inp.search_name,
            target_parameters=target_parameters,
            controls_search_name=self.inp.controls_search_name,
            controls_param_name=self.inp.controls_param_name,
            controls_value_format=self.inp.controls_value_format,
            controls_extra_parameters=self.inp.controls_extra_parameters,
            id_field=self.inp.id_field,
        )


# ---------------------------------------------------------------------------
# Result aggregation
# ---------------------------------------------------------------------------


def aggregate_results(
    ctx: TrialContext,
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
        sensitivity=_compute_sensitivity(ctx.inp.parameter_space, ctx.study),
        total_time_seconds=elapsed,
        status=status,
        error_message=error_message,
    )


# ---------------------------------------------------------------------------
# Progress emission
# ---------------------------------------------------------------------------


async def emit_trial_result(
    ctx: TrialContext,
    *,
    trial_num: int,
    trial_result: TrialResult,
    wdk_error: str = "",
) -> None:
    """Emit a progress event for a single trial (failed or successful)."""
    if not ctx.progress_callback:
        return

    await emit_trial_progress(
        ctx.progress_callback,
        TrialProgressEvent(
            optimization_id=ctx.optimization_id,
            trial_num=trial_num,
            budget=ctx.budget,
            trial=trial_result,
            best_trial=ctx.best_trial,
            recent_trials=ctx.trials[-5:],
            wdk_error=wdk_error,
        ),
    )


# ---------------------------------------------------------------------------
# Single-trial processing
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TrialOutcome:
    """Result of processing a single trial within the batch."""

    trial_result: TrialResult
    wdk_error: str
    grid_exhausted: bool
    is_failure: bool


@dataclass(frozen=True, slots=True)
class TrialEvalInput:
    """Inputs for a single trial evaluation (groups the per-trial data)."""

    ot: optuna.trial.Trial
    params: dict[str, ParamValue]
    wdk_result: ControlTestResult | None
    wdk_error: str
    trial_num: int
    n_positives: int
    n_negatives: int


def process_single_trial(
    ctx: TrialContext,
    inp: TrialEvalInput,
) -> TrialOutcome:
    """Process a single trial result: build TrialResult and report to Optuna."""
    if inp.wdk_result is None:
        ctx.study.tell(inp.ot, state=optuna.trial.TrialState.FAIL)
        return TrialOutcome(
            trial_result=_build_failed_trial(
                trial_number=inp.trial_num,
                params=inp.params,
                n_positives=inp.n_positives,
                n_negatives=inp.n_negatives,
            ),
            wdk_error=inp.wdk_error,
            grid_exhausted=False,
            is_failure=True,
        )

    trial_result = _build_successful_trial(
        trial_number=inp.trial_num,
        params=inp.params,
        wdk_result=inp.wdk_result,
        cfg=ctx.cfg,
        n_positives=inp.n_positives,
        n_negatives=inp.n_negatives,
    )

    grid_exhausted = False
    try:
        ctx.study.tell(inp.ot, trial_result.score)
    except RuntimeError as tell_exc:
        if "stop" in str(tell_exc).lower():
            logger.info(
                "Grid sampler exhausted search space",
                optimization_id=ctx.optimization_id,
                trial=inp.trial_num,
            )
            grid_exhausted = True
        else:
            raise

    return TrialOutcome(
        trial_result=trial_result,
        wdk_error=inp.wdk_error,
        grid_exhausted=grid_exhausted,
        is_failure=False,
    )


# ---------------------------------------------------------------------------
# Batch processing
# ---------------------------------------------------------------------------


@dataclass
class LoopState:
    """Mutable counters for the trial loop."""

    consecutive_failures: int = 0
    trials_since_improvement: int = 0
    abort_result: OptimizationResult | None = None


async def handle_failed_outcome(
    ctx: TrialContext,
    state: LoopState,
    outcome: TrialOutcome,
    trial_num: int,
) -> bool:
    """Handle a failed trial outcome. Returns True if the loop should abort."""
    state.consecutive_failures += 1
    await emit_trial_result(
        ctx,
        trial_num=trial_num,
        trial_result=outcome.trial_result,
        wdk_error=outcome.wdk_error,
    )
    abort_msg = _should_abort_on_failures(
        optimization_id=ctx.optimization_id,
        best_trial=ctx.best_trial,
        consecutive_failures=state.consecutive_failures,
        wdk_error=outcome.wdk_error,
    )
    if abort_msg:
        if ctx.progress_callback:
            await emit_error(
                ctx.progress_callback,
                optimization_id=ctx.optimization_id,
                error=abort_msg,
            )
        state.abort_result = aggregate_results(ctx, "error", abort_msg)
        return True
    return False


async def handle_successful_outcome(
    ctx: TrialContext,
    state: LoopState,
    outcome: TrialOutcome,
    trial_num: int,
) -> bool:
    """Handle a successful trial outcome. Returns True if the loop should stop."""
    state.consecutive_failures = 0
    if ctx.best_trial is None or outcome.trial_result.score > ctx.best_trial.score:
        ctx.best_trial = outcome.trial_result
        state.trials_since_improvement = 0
    else:
        state.trials_since_improvement += 1

    await emit_trial_result(
        ctx,
        trial_num=trial_num,
        trial_result=outcome.trial_result,
    )
    return outcome.grid_exhausted or _should_early_stop(
        optimization_id=ctx.optimization_id,
        best_trial=ctx.best_trial,
        trials_since_improvement=state.trials_since_improvement,
        trial_num=trial_num,
    )


@dataclass(frozen=True, slots=True)
class BatchInput:
    """Inputs for processing a batch of trials."""

    optuna_trials: list[optuna.trial.Trial]
    batch_params: list[dict[str, ParamValue]]
    wdk_results: list[tuple[ControlTestResult | None, str] | BaseException]
    trial_idx: int
    n_positives: int
    n_negatives: int


async def process_batch(
    ctx: TrialContext,
    state: LoopState,
    batch: BatchInput,
) -> bool:
    """Process all results in a batch. Returns True if the loop should stop."""
    for i, raw_result in enumerate(batch.wdk_results):
        trial_num = batch.trial_idx + i + 1
        wdk_result, wdk_error = _unpack_gather_result(
            raw_result,
            trial_num,
            batch.batch_params[i],
        )
        outcome = process_single_trial(
            ctx,
            TrialEvalInput(
                ot=batch.optuna_trials[i],
                params=batch.batch_params[i],
                wdk_result=wdk_result,
                wdk_error=wdk_error,
                trial_num=trial_num,
                n_positives=batch.n_positives,
                n_negatives=batch.n_negatives,
            ),
        )
        ctx.trials.append(outcome.trial_result)

        if outcome.is_failure:
            if await handle_failed_outcome(ctx, state, outcome, trial_num):
                return True
            continue

        if await handle_successful_outcome(ctx, state, outcome, trial_num):
            return True

    return False
