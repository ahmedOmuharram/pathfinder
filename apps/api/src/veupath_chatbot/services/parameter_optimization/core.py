"""Parameter optimization for VEuPathDB searches.

Optimizes search parameters against positive/negative control gene lists
using Bayesian optimization (TPE sampler via optuna), grid search, or random
search.  Each "trial" runs a temporary WDK strategy via
:func:`run_positive_negative_controls` and scores the result.
"""

from __future__ import annotations

import time
from typing import cast

import optuna

from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONArray, JSONObject, JSONValue
from veupath_chatbot.services.experiment.types import ControlValueFormat
from veupath_chatbot.services.parameter_optimization.callbacks import (
    emit_completed,
    emit_started,
)
from veupath_chatbot.services.parameter_optimization.config import (
    CancelCheck,
    OptimizationConfig,
    OptimizationResult,
    ParameterSpec,
    ProgressCallback,
)
from veupath_chatbot.services.parameter_optimization.trials import (
    _create_sampler,
    _TrialContext,
    run_trial_loop,
)

logger = get_logger(__name__)

# Silence optuna's internal logging (we emit our own progress events).
optuna.logging.set_verbosity(optuna.logging.WARNING)


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
    start_time = time.monotonic()

    sampler, budget = _create_sampler(cfg, parameter_space, cfg.budget)

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
        await emit_started(
            progress_callback,
            optimization_id=optimization_id,
            search_name=search_name,
            record_type=record_type,
            budget=budget,
            objective=cfg.objective,
            positive_controls_count=len(positive_controls or []),
            negative_controls_count=len(negative_controls or []),
            param_space_json=param_space_json,
        )

    study = optuna.create_study(direction="maximize", sampler=sampler)

    ctx = _TrialContext(
        site_id=site_id,
        record_type=record_type,
        search_name=search_name,
        fixed_parameters=fixed_parameters,
        parameter_space=parameter_space,
        controls_search_name=controls_search_name,
        controls_param_name=controls_param_name,
        positive_controls=positive_controls,
        negative_controls=negative_controls,
        controls_value_format=controls_value_format,
        controls_extra_parameters=controls_extra_parameters,
        id_field=id_field,
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
            optimization_id=optimization_id,
            status=result.status,
            budget=budget,
            trials=result.all_trials,
            best_trial=result.best_trial,
            pareto=result.pareto_frontier,
            sensitivity=result.sensitivity,
            elapsed=result.total_time_seconds,
        )

    return result
