"""Optimization phases: parameter optimization and tree-knob optimization.

These phases attempt to improve experiment metrics by searching the
parameter space (single-step) or adjusting thresholds and boolean
operators across a strategy tree (multi-step).
"""

from pydantic import JsonValue

from pathfinder.domain.strategy.ast import StrategyStepNode
from pathfinder.platform.errors import AppError
from pathfinder.platform.logging import get_logger
from pathfinder.platform.types import JSONObject
from pathfinder.services.experiment.helpers import ControlsContext
from pathfinder.services.experiment.service.context import PhaseContext
from pathfinder.services.experiment.service.shared import (
    apply_control_result,
    run_single_step_controls,
)
from pathfinder.services.experiment.tree_knobs import (
    TreeOptimizationOptions,
    optimize_tree_knobs,
)
from pathfinder.services.experiment.types import (
    ControlTestResult,
    ExperimentMetrics,
    OptimizationSpec,
)
from pathfinder.services.parameter_optimization import (
    OptimizationConfig,
    OptimizationInput,
    ParameterSpec,
    optimize_search_parameters,
)

logger = get_logger(__name__)

def _spec_optimizable(s: OptimizationSpec) -> bool:
    if s.type == "categorical":
        choices = s.choices or []
        valid = [c for c in choices if isinstance(c, str) and c.strip()]
        return len(valid) > 0
    return True

async def phase_optimize_parameters(
    pctx: PhaseContext,
    metrics: ExperimentMetrics,
) -> tuple[ControlTestResult | None, ExperimentMetrics]:
    """Run parameter optimization and optionally re-evaluate with best params.

    :returns: ``(updated_result_or_None, updated_metrics)``.
    """
    config, experiment = pctx.config, pctx.experiment

    await pctx.emit("evaluating", message="Running parameter optimization...")

    optimizable_specs = [
        s for s in (config.optimization_specs or []) if _spec_optimizable(s)
    ]
    optimizable_names = {s.name for s in optimizable_specs}

    if not optimizable_specs:
        logger.info("Skipping parameter optimization: no params with valid space")
        return None, metrics

    opt_param_space = [
        ParameterSpec(
            name=s.name,
            type=s.type,
            min=s.min,
            max=s.max,
            step=s.step,
            choices=s.choices,
        )
        for s in optimizable_specs
    ]

    fixed_params: dict[str, JsonValue] = {
        k: v
        for k, v in config.parameters.items()
        if k not in optimizable_names and v not in ("", None)
    }

    async def _opt_progress(event: JSONObject) -> None:
        trial_data = event.get("data", {})
        trial_num = (
            trial_data.get("currentTrial", "?") if isinstance(trial_data, dict) else "?"
        )
        await pctx.emit(
            "optimizing",
            message=f"Trial {trial_num} / {config.optimization_budget}",
            trialProgress=event.get("data"),
        )

    opt_result = await optimize_search_parameters(
        OptimizationInput(
            site_id=config.site_id,
            record_type=config.record_type,
            search_name=config.search_name,
            fixed_parameters=fixed_params,
            parameter_space=opt_param_space,
            controls_search_name=config.controls_search_name,
            controls_param_name=config.controls_param_name,
            positive_controls=config.positive_controls or None,
            negative_controls=config.negative_controls or None,
            controls_value_format=config.controls_value_format,
        ),
        config=OptimizationConfig(
            budget=config.optimization_budget,
            objective=config.optimization_objective,
        ),
        progress_callback=_opt_progress,
    )

    experiment.optimization_result = opt_result.model_dump(by_alias=True, mode="json")

    if opt_result.best_trial:
        optimized_params = dict(config.parameters)
        optimized_params.update(opt_result.best_trial.parameters)
        await pctx.emit(
            "evaluating",
            message="Optimization complete — re-evaluating with best parameters",
        )

        result = await run_single_step_controls(config, optimized_params)
        metrics = await apply_control_result(config, experiment, result)
        return result, metrics

    return None, metrics

async def phase_optimize_tree_knobs(
    pctx: PhaseContext,
    tree: StrategyStepNode,
) -> None:
    """Optimize threshold parameters and boolean operators across a strategy tree."""
    config, experiment = pctx.config, pctx.experiment
    try:
        await pctx.emit("optimizing", message="Optimizing strategy tree knobs...")

        ctx = ControlsContext.from_config(config)
        tree_opt_result = await optimize_tree_knobs(
            ctx,
            tree,
            config.threshold_knobs or [],
            config.operator_knobs or [],
            TreeOptimizationOptions(
                objective=config.tree_optimization_objective,
                budget=config.tree_optimization_budget,
                max_list_size=config.max_list_size,
            ),
        )
        experiment.tree_optimization = tree_opt_result
        pctx.store.save(experiment)
        await pctx.emit(
            "optimizing",
            message=f"Tree optimization complete — best score: {tree_opt_result.best_trial.score:.4f}"
            if tree_opt_result.best_trial
            else "Tree optimization complete — no improving trial found",
        )
    except AppError as exc:
        logger.warning(
            "Tree knob optimization failed",
            experiment_id=experiment.id,
            error=str(exc),
        )
