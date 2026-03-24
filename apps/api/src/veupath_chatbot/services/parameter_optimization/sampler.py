"""Optuna sampler creation and parameter suggestion for optimization."""

import optuna

from veupath_chatbot.platform.types import JSONValue
from veupath_chatbot.services.parameter_optimization.config import (
    OptimizationConfig,
    ParameterSpec,
)


def _create_sampler(
    cfg: OptimizationConfig,
    parameter_space: list[ParameterSpec],
    budget: int,
) -> tuple[optuna.samplers.BaseSampler, int]:
    """Create an Optuna sampler and (possibly adjusted) budget.

    Grid search may reduce *budget* if the total number of combinations
    is smaller than the requested budget.
    """
    if cfg.method == "grid":
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
    if cfg.method == "random":
        return optuna.samplers.RandomSampler(seed=42), budget
    # "bayesian" or any unrecognised method → TPE
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
