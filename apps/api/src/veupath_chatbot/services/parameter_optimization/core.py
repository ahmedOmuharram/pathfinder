"""Parameter optimization for VEuPathDB searches.

Optimizes search parameters against positive/negative control gene lists
using Bayesian optimization (TPE sampler via optuna), grid search, or random
search.  Each "trial" runs a temporary WDK strategy via
:func:`run_positive_negative_controls` and scores the result.
"""

import time
from typing import cast

import optuna

from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONArray, JSONValue
from veupath_chatbot.services.parameter_optimization.callbacks import (
    OptimizationCompletedEvent,
    OptimizationStartedEvent,
    emit_completed,
    emit_started,
)
from veupath_chatbot.services.parameter_optimization.config import (
    CancelCheck,
    OptimizationConfig,
    OptimizationInput,
    OptimizationResult,
    ProgressCallback,
)
from veupath_chatbot.services.parameter_optimization.sampler import (
    _create_sampler,
)
from veupath_chatbot.services.parameter_optimization.trials import (
    _TrialContext,
    run_trial_loop,
)

logger = get_logger(__name__)

# Silence optuna's internal logging (we emit our own progress events).
optuna.logging.set_verbosity(optuna.logging.WARNING)


async def optimize_search_parameters(
    inp: OptimizationInput,
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
    start_time = time.monotonic()

    sampler, budget = _create_sampler(cfg, inp.parameter_space, cfg.budget)

    param_space_json: JSONArray = [
        {
            "name": p.name,
            "type": p.param_type,
            "minValue": p.min_value,
            "maxValue": p.max_value,
            "logScale": p.log_scale,
            "choices": cast("JSONValue", p.choices),
        }
        for p in inp.parameter_space
    ]

    if progress_callback:
        await emit_started(
            progress_callback,
            OptimizationStartedEvent(
                optimization_id=optimization_id,
                search_name=inp.search_name,
                record_type=inp.record_type,
                budget=budget,
                objective=cfg.objective,
                positive_controls_count=len(inp.positive_controls or []),
                negative_controls_count=len(inp.negative_controls or []),
                parameter_space=param_space_json,
            ),
        )

    study = optuna.create_study(direction="maximize", sampler=sampler)

    ctx = _TrialContext(
        inp=inp,
        cfg=cfg,
        optimization_id=optimization_id,
        budget=budget,
        study=study,
        progress_callback=progress_callback,
        check_cancelled=check_cancelled,
        start_time=start_time,
        trials=[],
    )

    result = await run_trial_loop(ctx)

    if progress_callback and result.status != "error":
        await emit_completed(
            progress_callback,
            OptimizationCompletedEvent(
                optimization_id=optimization_id,
                status=result.status,
                budget=budget,
                all_trials=result.all_trials,
                best_trial=result.best_trial,
                pareto_frontier=result.pareto_frontier,
                sensitivity=result.sensitivity,
                total_time_seconds=result.total_time_seconds,
            ),
        )

    return result
