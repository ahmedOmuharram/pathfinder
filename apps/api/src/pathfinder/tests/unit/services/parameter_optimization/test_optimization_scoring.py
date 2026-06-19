from __future__ import annotations

import optuna
import pytest

from pathfinder.services.parameter_optimization.config import (
    OptimizationConfig,
    ParameterSpec,
    TrialResult,
)
from pathfinder.services.parameter_optimization.scoring import (
    _compute_pareto_frontier,
    _compute_score,
    _compute_sensitivity,
    _score_mcc,
)


def _trial(
    n: int,
    *,
    recall: float | None,
    fpr: float | None,
) -> TrialResult:
    return TrialResult(
        trial_number=n,
        parameters={},
        score=0.0,
        recall=recall,
        false_positive_rate=fpr,
        estimated_size=None,
    )


class TestScoreMcc:
    def test_balanced_case_matches_closed_form(self) -> None:
        assert _score_mcc(0.8, 0.9, 0.1) == pytest.approx(0.7035264706814485)

    def test_perfect_classifier_is_one(self) -> None:
        assert _score_mcc(1.0, 1.0, 0.0) == pytest.approx(1.0)

    def test_zero_denominator_guard_returns_zero(self) -> None:
        assert _score_mcc(0.0, 1.0, 0.0) == 0.0


class TestComputeScoreByObjective:
    def test_f1_uses_precision_from_intersection_hits(self) -> None:
        cfg = OptimizationConfig(objective="f1")
        score = _compute_score(0.6, 0.1, cfg, positive_hits=30, negative_hits=10)
        assert score == pytest.approx(0.6666666666666665)

    def test_f_beta_weights_recall_with_beta(self) -> None:
        cfg = OptimizationConfig(objective="f_beta", beta=2.0)
        score = _compute_score(0.6, 0.1, cfg, positive_hits=30, negative_hits=10)
        assert score == pytest.approx(0.625)

    def test_balanced_accuracy_is_mean_of_recall_and_specificity(self) -> None:
        cfg = OptimizationConfig(objective="balanced_accuracy")
        assert _compute_score(0.6, 0.1, cfg) == pytest.approx(0.75)

    def test_youdens_j_is_recall_plus_specificity_minus_one(self) -> None:
        cfg = OptimizationConfig(objective="youdens_j")
        assert _compute_score(0.6, 0.1, cfg) == pytest.approx(0.5)

    def test_custom_blends_recall_against_raw_fpr(self) -> None:
        cfg = OptimizationConfig(
            objective="custom", recall_weight=1.0, precision_weight=1.0
        )
        assert _compute_score(0.6, 0.1, cfg) == pytest.approx(0.5)

    def test_precision_falls_back_to_specificity_without_hits(self) -> None:
        cfg = OptimizationConfig(objective="precision")
        assert _compute_score(0.6, 0.1, cfg) == pytest.approx(0.9)

    def test_none_recall_and_fpr_score_zero_for_f1(self) -> None:
        cfg = OptimizationConfig(objective="f1")
        assert _compute_score(None, None, cfg) == 0.0


class TestEstimatedSizePenalty:
    def test_penalty_subtracts_size_fraction_of_default_genome(self) -> None:
        cfg = OptimizationConfig(objective="f1", estimated_size_penalty=0.1)
        score = _compute_score(
            0.6, 0.1, cfg, estimated_size=5000, positive_hits=30, negative_hits=10
        )
        assert score == pytest.approx(0.6416666666666665)

    def test_penalty_clamps_at_zero(self) -> None:
        cfg = OptimizationConfig(objective="recall", estimated_size_penalty=5.0)
        assert _compute_score(0.05, 0.5, cfg, estimated_size=20_000) == 0.0

    def test_no_penalty_when_weight_zero(self) -> None:
        cfg = OptimizationConfig(objective="recall", estimated_size_penalty=0.0)
        assert _compute_score(0.6, 0.1, cfg, estimated_size=999_999) == pytest.approx(
            0.6
        )


class TestParetoFrontier:
    def test_drops_dominated_trials(self) -> None:
        a = _trial(0, recall=0.9, fpr=0.5)
        b = _trial(1, recall=0.8, fpr=0.3)
        c = _trial(2, recall=0.7, fpr=0.4)
        d = _trial(3, recall=0.6, fpr=0.1)
        frontier = _compute_pareto_frontier([c, a, d, b])
        assert [t.trial_number for t in frontier] == [0, 1, 3]

    def test_ignores_trials_missing_recall_or_fpr(self) -> None:
        good = _trial(0, recall=0.8, fpr=0.2)
        no_recall = _trial(1, recall=None, fpr=0.1)
        no_fpr = _trial(2, recall=0.9, fpr=None)
        frontier = _compute_pareto_frontier([good, no_recall, no_fpr])
        assert [t.trial_number for t in frontier] == [0]

    def test_empty_input_returns_empty(self) -> None:
        assert _compute_pareto_frontier([]) == []


class TestSensitivityFallbacks:
    def test_no_study_returns_zero_for_every_param(self) -> None:
        specs = [
            ParameterSpec(name="alpha", type="numeric", min=0.0, max=1.0),
            ParameterSpec(name="beta", type="integer", min=0, max=10),
        ]
        assert _compute_sensitivity(specs, study=None) == {"alpha": 0.0, "beta": 0.0}

    def test_fewer_than_two_completed_trials_returns_zeros(self) -> None:
        specs = [ParameterSpec(name="alpha", type="numeric", min=0.0, max=1.0)]
        study = optuna.create_study(direction="maximize")
        dist: dict[str, optuna.distributions.BaseDistribution] = {
            "alpha": optuna.distributions.FloatDistribution(0.0, 1.0)
        }
        study.add_trial(
            optuna.trial.create_trial(
                params={"alpha": 0.5}, distributions=dist, value=1.0
            )
        )
        assert _compute_sensitivity(specs, study=study) == {"alpha": 0.0}

    def test_real_study_normalizes_and_surfaces_dominant_param(self) -> None:
        specs = [
            ParameterSpec(name="driver", type="numeric", min=0.0, max=1.0),
            ParameterSpec(name="noise", type="numeric", min=0.0, max=1.0),
        ]
        study = optuna.create_study(direction="maximize")
        dist: dict[str, optuna.distributions.BaseDistribution] = {
            "driver": optuna.distributions.FloatDistribution(0.0, 1.0),
            "noise": optuna.distributions.FloatDistribution(0.0, 1.0),
        }
        for i in range(12):
            study.add_trial(
                optuna.trial.create_trial(
                    params={"driver": i / 11.0, "noise": (i * 7 % 12) / 11.0},
                    distributions=dist,
                    value=i / 11.0,
                )
            )
        importances = _compute_sensitivity(specs, study=study)
        assert set(importances) == {"driver", "noise"}
        assert all(0.0 <= v <= 1.0 for v in importances.values())
        assert sum(importances.values()) == pytest.approx(1.0, abs=1e-6)
        assert importances["driver"] > importances["noise"]
