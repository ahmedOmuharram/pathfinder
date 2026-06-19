from __future__ import annotations

import optuna

from pathfinder.domain.parameters.values import NumberValue, SinglePickValue
from pathfinder.services.parameter_optimization.config import (
    OptimizationConfig,
    ParameterSpec,
)
from pathfinder.services.parameter_optimization.sampler import (
    _create_sampler,
    _suggest_trial_params,
)


class TestCreateSampler:
    def test_bayesian_uses_tpe_and_keeps_budget(self) -> None:
        sampler, budget = _create_sampler(
            OptimizationConfig(method="bayesian"), [], budget=30
        )
        assert isinstance(sampler, optuna.samplers.TPESampler)
        assert budget == 30

    def test_random_uses_random_sampler_and_keeps_budget(self) -> None:
        sampler, budget = _create_sampler(
            OptimizationConfig(method="random"), [], budget=25
        )
        assert isinstance(sampler, optuna.samplers.RandomSampler)
        assert budget == 25

    def test_grid_caps_budget_at_total_combinations(self) -> None:
        # categorical 3 choices x integer {0,5,10} (range(0,11,5)) = 9 combos,
        # which is below the requested 30 → budget shrinks to 9.
        space = [
            ParameterSpec(name="c", type="categorical", choices=["a", "b", "c"]),
            ParameterSpec(name="n", type="integer", min=0, max=10, step=5),
        ]
        sampler, budget = _create_sampler(
            OptimizationConfig(method="grid"), space, budget=30
        )
        assert isinstance(sampler, optuna.samplers.GridSampler)
        assert budget == 9

    def test_grid_keeps_budget_when_combinations_exceed_it(self) -> None:
        # categorical 5 by integer {0..10 step 1} = 5 * 11 = 55 combos > 30 -> 30.
        space = [
            ParameterSpec(
                name="c", type="categorical", choices=["a", "b", "c", "d", "e"]
            ),
            ParameterSpec(name="n", type="integer", min=0, max=10),
        ]
        _, budget = _create_sampler(OptimizationConfig(method="grid"), space, budget=30)
        assert budget == 30

    def test_grid_numeric_uses_budget_levels(self) -> None:
        # one numeric param → min(10, budget=5) = 5 grid levels → 5 combos.
        space = [ParameterSpec(name="x", type="numeric", min=0.0, max=1.0)]
        _, budget = _create_sampler(OptimizationConfig(method="grid"), space, budget=5)
        assert budget == 5


class TestSuggestTrialParams:
    def test_numeric_wraps_suggested_float(self) -> None:
        space = [ParameterSpec(name="weight", type="numeric", min=0.0, max=1.0)]
        trial = optuna.trial.FixedTrial({"weight": 0.42})
        params = _suggest_trial_params(trial, space)
        assert params == {"weight": NumberValue(value=0.42)}

    def test_integer_wraps_suggested_int_as_float(self) -> None:
        space = [ParameterSpec(name="count", type="integer", min=0, max=100)]
        trial = optuna.trial.FixedTrial({"count": 7})
        params = _suggest_trial_params(trial, space)
        assert params == {"count": NumberValue(value=7.0)}

    def test_categorical_wraps_suggested_choice(self) -> None:
        space = [
            ParameterSpec(name="organism", type="categorical", choices=["pf", "tg"])
        ]
        trial = optuna.trial.FixedTrial({"organism": "tg"})
        params = _suggest_trial_params(trial, space)
        assert params == {"organism": SinglePickValue(value="tg")}

    def test_suggests_one_value_per_spec(self) -> None:
        space = [
            ParameterSpec(name="weight", type="numeric", min=0.0, max=1.0),
            ParameterSpec(name="count", type="integer", min=0, max=100),
            ParameterSpec(name="organism", type="categorical", choices=["pf", "tg"]),
        ]
        trial = optuna.trial.FixedTrial({"weight": 0.1, "count": 3, "organism": "pf"})
        params = _suggest_trial_params(trial, space)
        assert params == {
            "weight": NumberValue(value=0.1),
            "count": NumberValue(value=3.0),
            "organism": SinglePickValue(value="pf"),
        }
