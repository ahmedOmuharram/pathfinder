"""Extended tests for veupath_chatbot.services.parameter_optimization.

Covers pure functions, edge cases, serialization, config defaults, scoring
corner cases, trial generation, sampler creation, callback payloads, and
the Pareto frontier algorithm in depth.  All WDK calls are mocked.
"""

from typing import Any, cast
from unittest.mock import AsyncMock, patch

import optuna
import pytest

from veupath_chatbot.platform.types import JSONArray, JSONObject, JSONValue
from veupath_chatbot.services.parameter_optimization.callbacks import (
    OptimizationCompletedEvent,
    OptimizationStartedEvent,
    TrialProgressEvent,
    emit_completed,
    emit_error,
    emit_started,
    emit_trial_progress,
)
from veupath_chatbot.services.parameter_optimization.config import (
    OptimizationConfig,
    OptimizationInput,
    OptimizationResult,
    ParameterSpec,
    TrialResult,
)
from veupath_chatbot.services.parameter_optimization.core import (
    optimize_search_parameters,
)
from veupath_chatbot.services.parameter_optimization.scoring import (
    _compute_pareto_frontier,
    _compute_score,
    _compute_sensitivity,
    _to_float,
    _to_int,
    _trial_to_json,
    result_to_json,
)
from veupath_chatbot.services.parameter_optimization.trials import (
    _create_sampler,
    _suggest_trial_params,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _trial(
    *,
    trial_number: int = 1,
    score: float = 0.5,
    recall: float | None = 0.8,
    fpr: float | None = 0.1,
    result_count: int | None = 100,
    parameters: dict[str, JSONValue] | None = None,
) -> TrialResult:
    return TrialResult(
        trial_number=trial_number,
        parameters=parameters or {},
        score=score,
        recall=recall,
        false_positive_rate=fpr,
        result_count=result_count,
    )


def _make_wdk_result(
    *,
    result_count: int = 100,
    pos_recall: float = 0.8,
    neg_fpr: float = 0.1,
    positive_controls: list[str] | None = None,
    negative_controls: list[str] | None = None,
) -> JSONObject:
    pos = positive_controls or [f"POS_{i}" for i in range(10)]
    neg = negative_controls or [f"NEG_{i}" for i in range(8)]
    n_pos_found = int(len(pos) * pos_recall)
    n_neg_found = int(len(neg) * neg_fpr)
    pos_found_ids = pos[:n_pos_found]
    neg_found_ids = neg[:n_neg_found]
    return {
        "siteId": "plasmodb",
        "recordType": "transcript",
        "target": {
            "searchName": "GenesByRNASeq",
            "parameters": {},
            "stepId": 999,
            "resultCount": result_count,
        },
        "positive": {
            "controlsCount": len(pos),
            "intersectionCount": n_pos_found,
            "intersectionIdsSample": cast("JSONArray", pos_found_ids[:50]),
            "intersectionIds": cast("JSONArray", pos_found_ids),
            "missingIdsSample": cast(
                "JSONArray", [x for x in pos if x not in pos_found_ids][:50]
            ),
            "recall": n_pos_found / len(pos) if n_pos_found > 0 else None,
        },
        "negative": {
            "controlsCount": len(neg),
            "intersectionCount": n_neg_found,
            "intersectionIdsSample": cast("JSONArray", neg_found_ids[:50]),
            "intersectionIds": cast("JSONArray", neg_found_ids),
            "unexpectedHitsSample": cast("JSONArray", neg_found_ids[:50]),
            "falsePositiveRate": n_neg_found / len(neg) if n_neg_found > 0 else None,
        },
    }


def _common_inp(
    parameter_space: list[ParameterSpec],
    **overrides: Any,
) -> OptimizationInput:
    """Build a minimal OptimizationInput for testing with optional overrides."""
    defaults: dict[str, Any] = {
        "site_id": "plasmodb",
        "record_type": "transcript",
        "search_name": "TestSearch",
        "fixed_parameters": cast("JSONObject", {"organism": "P. falciparum"}),
        "controls_search_name": "GeneByLocusTag",
        "controls_param_name": "ds_gene_ids",
        "positive_controls": [f"POS_{i}" for i in range(10)],
        "negative_controls": [f"NEG_{i}" for i in range(8)],
    }
    defaults.update(overrides)
    return OptimizationInput(parameter_space=parameter_space, **defaults)


WDK_PATCH = (
    "veupath_chatbot.services.parameter_optimization.trials"
    ".run_positive_negative_controls"
)


# ===================================================================
# _to_float / _to_int coercion helpers
# ===================================================================


class TestToFloat:
    def test_none_returns_none(self) -> None:
        assert _to_float(None) is None

    def test_int_coerces(self) -> None:
        assert _to_float(5) == 5.0
        assert isinstance(_to_float(5), float)

    def test_float_returns_float(self) -> None:
        assert _to_float(3.14) == 3.14

    def test_zero(self) -> None:
        assert _to_float(0) == 0.0

    def test_negative(self) -> None:
        assert _to_float(-2.5) == -2.5

    def test_string_returns_none(self) -> None:
        assert _to_float("0.5") is None

    def test_bool_coerces(self) -> None:
        # bool is a subclass of int in Python
        result = _to_float(True)
        assert result == 1.0

    def test_list_returns_none(self) -> None:
        assert _to_float([1, 2]) is None

    def test_dict_returns_none(self) -> None:
        assert _to_float({"a": 1}) is None


class TestToInt:
    def test_none_returns_none(self) -> None:
        assert _to_int(None) is None

    def test_int_returns_int(self) -> None:
        assert _to_int(7) == 7
        assert isinstance(_to_int(7), int)

    def test_float_truncates(self) -> None:
        assert _to_int(3.9) == 3

    def test_zero(self) -> None:
        assert _to_int(0) == 0

    def test_negative(self) -> None:
        assert _to_int(-4) == -4

    def test_string_returns_none(self) -> None:
        assert _to_int("7") is None

    def test_bool_coerces(self) -> None:
        assert _to_int(True) == 1
        assert _to_int(False) == 0

    def test_list_returns_none(self) -> None:
        assert _to_int([1]) is None


# ===================================================================
# _compute_score — exhaustive objective coverage
# ===================================================================


class TestComputeScoreObjectives:
    """Test every OptimizationObjective variant and edge cases."""

    # --- recall ---

    def test_recall_returns_recall_directly(self) -> None:
        cfg = OptimizationConfig(objective="recall")
        assert _compute_score(0.65, 0.9, cfg) == 0.65

    def test_recall_none_defaults_to_zero(self) -> None:
        cfg = OptimizationConfig(objective="recall")
        assert _compute_score(None, 0.3, cfg) == 0.0

    # --- precision ---

    def test_precision_uses_specificity_when_no_hits(self) -> None:
        cfg = OptimizationConfig(objective="precision")
        # precision falls back to specificity = 1 - fpr
        assert _compute_score(0.5, 0.2, cfg) == pytest.approx(0.8)

    def test_precision_uses_true_ppv_when_hits_available(self) -> None:
        cfg = OptimizationConfig(objective="precision")
        # TP=8, FP=2 => precision = 8/10 = 0.8
        score = _compute_score(0.5, 0.2, cfg, positive_hits=8, negative_hits=2)
        assert score == pytest.approx(0.8)

    def test_precision_zero_hits_gives_zero(self) -> None:
        cfg = OptimizationConfig(objective="precision")
        score = _compute_score(0.5, 0.2, cfg, positive_hits=0, negative_hits=0)
        assert score == 0.0

    # --- specificity ---

    def test_specificity_perfect(self) -> None:
        cfg = OptimizationConfig(objective="specificity")
        assert _compute_score(0.5, 0.0, cfg) == 1.0

    def test_specificity_worst(self) -> None:
        cfg = OptimizationConfig(objective="specificity")
        assert _compute_score(0.5, 1.0, cfg) == 0.0

    def test_specificity_with_none_fpr(self) -> None:
        cfg = OptimizationConfig(objective="specificity")
        # fpr=None => raw_fpr=0.0 => specificity=1.0
        assert _compute_score(0.5, None, cfg) == 1.0

    # --- balanced_accuracy ---

    def test_balanced_accuracy_perfect(self) -> None:
        cfg = OptimizationConfig(objective="balanced_accuracy")
        assert _compute_score(1.0, 0.0, cfg) == 1.0

    def test_balanced_accuracy_half(self) -> None:
        cfg = OptimizationConfig(objective="balanced_accuracy")
        # recall=0.6, specificity=1-0.4=0.6 => (0.6+0.6)/2 = 0.6
        assert _compute_score(0.6, 0.4, cfg) == pytest.approx(0.6)

    def test_balanced_accuracy_worst(self) -> None:
        cfg = OptimizationConfig(objective="balanced_accuracy")
        assert _compute_score(0.0, 1.0, cfg) == 0.0

    # --- mcc ---

    def test_mcc_perfect(self) -> None:
        cfg = OptimizationConfig(objective="mcc")
        score = _compute_score(1.0, 0.0, cfg)
        assert score == pytest.approx(1.0)

    def test_mcc_worst(self) -> None:
        cfg = OptimizationConfig(objective="mcc")
        # recall=0, fpr=1 => tpr=0, tnr=0, fpr=1, fnr=1
        # num = 0*0 - 1*1 = -1
        # denom = sqrt((0+1)*(0+1)*(0+1)*(0+1)) = 1
        # MCC should be -1
        score = _compute_score(0.0, 1.0, cfg)
        assert score == pytest.approx(-1.0)

    def test_mcc_random_classifier(self) -> None:
        cfg = OptimizationConfig(objective="mcc")
        # recall=0.5, fpr=0.5 => tpr=0.5, tnr=0.5, fpr=0.5, fnr=0.5
        # num = 0.5*0.5 - 0.5*0.5 = 0
        score = _compute_score(0.5, 0.5, cfg)
        assert score == pytest.approx(0.0)

    def test_mcc_degenerate_denom_zero(self) -> None:
        cfg = OptimizationConfig(objective="mcc")
        # recall=0, fpr=0 => tpr=0, tnr=1, fpr=0, fnr=1
        # denom = sqrt((0+0)*(0+1)*(1+0)*(1+1)) = sqrt(0) = 0
        score = _compute_score(0.0, 0.0, cfg)
        assert score == 0.0  # protected by denom > 1e-10 check

    # --- youdens_j ---

    def test_youdens_j_perfect(self) -> None:
        cfg = OptimizationConfig(objective="youdens_j")
        assert _compute_score(1.0, 0.0, cfg) == 1.0

    def test_youdens_j_random(self) -> None:
        cfg = OptimizationConfig(objective="youdens_j")
        # recall + specificity - 1 = 0.5 + 0.5 - 1 = 0
        assert _compute_score(0.5, 0.5, cfg) == pytest.approx(0.0)

    def test_youdens_j_worst(self) -> None:
        cfg = OptimizationConfig(objective="youdens_j")
        # 0 + 0 - 1 = -1
        assert _compute_score(0.0, 1.0, cfg) == -1.0

    # --- f1 ---

    def test_f1_with_true_precision(self) -> None:
        cfg = OptimizationConfig(objective="f1")
        # TP=9, FP=1 => precision=0.9, recall=0.9
        # F1 = 2*0.9*0.9 / (0.9+0.9) = 0.9
        score = _compute_score(0.9, 0.1, cfg, positive_hits=9, negative_hits=1)
        assert score == pytest.approx(0.9)

    def test_f1_zero_precision_and_recall(self) -> None:
        cfg = OptimizationConfig(objective="f1")
        score = _compute_score(0.0, 1.0, cfg)
        assert score == 0.0

    # --- f_beta ---

    def test_f_beta_with_beta_1_equals_f1(self) -> None:
        cfg_f1 = OptimizationConfig(objective="f1")
        cfg_fb = OptimizationConfig(objective="f_beta", beta=1.0)
        score_f1 = _compute_score(0.7, 0.2, cfg_f1)
        score_fb = _compute_score(0.7, 0.2, cfg_fb)
        assert score_fb == pytest.approx(score_f1)

    def test_f_beta_high_beta_favors_recall(self) -> None:
        cfg = OptimizationConfig(objective="f_beta", beta=5.0)
        # High beta => heavily weights recall
        score_high_recall = _compute_score(0.9, 0.5, cfg)
        score_low_recall = _compute_score(0.3, 0.0, cfg)
        assert score_high_recall > score_low_recall

    def test_f_beta_zero_denom(self) -> None:
        cfg = OptimizationConfig(objective="f_beta", beta=2.0)
        # recall=0, precision=0 (fpr=1 => specificity=0, no hits) => denom=0
        score = _compute_score(0.0, 1.0, cfg)
        assert score == 0.0

    # --- custom ---

    def test_custom_default_weights(self) -> None:
        cfg = OptimizationConfig(
            objective="custom", recall_weight=1.0, precision_weight=1.0
        )
        # base is 1.0 * recall - 1.0 * fpr
        score = _compute_score(0.8, 0.3, cfg)
        assert score == pytest.approx(0.5)

    def test_custom_asymmetric_weights(self) -> None:
        cfg = OptimizationConfig(
            objective="custom", recall_weight=2.0, precision_weight=0.5
        )
        score = _compute_score(0.8, 0.4, cfg)
        # 2.0*0.8 - 0.5*0.4 = 1.6 - 0.2 = 1.4
        assert score == pytest.approx(1.4)

    def test_custom_can_go_negative_before_penalty_clamp(self) -> None:
        cfg = OptimizationConfig(
            objective="custom", recall_weight=0.1, precision_weight=2.0
        )
        # 0.1*0.1 - 2.0*0.9 = 0.01 - 1.8 = -1.79
        # No penalty applied => no floor, returns negative
        score = _compute_score(0.1, 0.9, cfg)
        assert score < 0

    # --- unknown objective falls back to recall ---

    def test_unknown_objective_falls_back_to_recall(self) -> None:
        cfg = OptimizationConfig()
        # Hack the objective to a nonsense value
        object.__setattr__(cfg, "objective", "nonexistent")
        score = _compute_score(0.75, 0.3, cfg)
        assert score == 0.75


class TestComputeScoreResultCountPenalty:
    """Detailed tests for the result_count_penalty mechanism."""

    def test_no_penalty_when_result_count_none(self) -> None:
        cfg = OptimizationConfig(objective="recall", result_count_penalty=0.5)
        score = _compute_score(0.8, 0.1, cfg, result_count=None)
        assert score == 0.8

    def test_no_penalty_when_result_count_zero(self) -> None:
        cfg = OptimizationConfig(objective="recall", result_count_penalty=0.5)
        score = _compute_score(0.8, 0.1, cfg, result_count=0)
        assert score == 0.8

    def test_penalty_scales_with_count(self) -> None:
        cfg = OptimizationConfig(objective="recall", result_count_penalty=1.0)
        # penalty = 1.0 * (1000 / 20000) = 0.05
        score = _compute_score(0.8, 0.0, cfg, result_count=1000)
        assert score == pytest.approx(0.75)

    def test_penalty_never_below_zero(self) -> None:
        cfg = OptimizationConfig(objective="recall", result_count_penalty=1.0)
        score = _compute_score(0.1, 0.0, cfg, result_count=100_000)
        assert score == 0.0

    def test_penalty_with_negative_weight_does_nothing(self) -> None:
        # result_count_penalty < 0 => condition `> 0` is False => no penalty
        cfg = OptimizationConfig(objective="recall", result_count_penalty=-1.0)
        score = _compute_score(0.8, 0.0, cfg, result_count=10000)
        assert score == 0.8


class TestComputeScorePrecisionFromHits:
    """Test the true precision (PPV) path when positive_hits/negative_hits are given."""

    def test_ppv_all_true_positives(self) -> None:
        cfg = OptimizationConfig(objective="f1")
        # TP=10, FP=0 => precision=1.0, recall=0.8
        # F1 = 2*1.0*0.8/(1.0+0.8) = 1.6/1.8 ~ 0.8889
        score = _compute_score(0.8, 0.0, cfg, positive_hits=10, negative_hits=0)
        assert score == pytest.approx(2 * 1.0 * 0.8 / (1.0 + 0.8))

    def test_ppv_all_false_positives(self) -> None:
        cfg = OptimizationConfig(objective="f1")
        # TP=0, FP=10 => precision=0.0, recall=0
        score = _compute_score(0.0, 0.5, cfg, positive_hits=0, negative_hits=10)
        assert score == 0.0

    def test_ppv_mixed(self) -> None:
        cfg = OptimizationConfig(objective="precision")
        # TP=7, FP=3 => precision=0.7
        score = _compute_score(0.7, 0.3, cfg, positive_hits=7, negative_hits=3)
        assert score == pytest.approx(0.7)


# ===================================================================
# _compute_pareto_frontier
# ===================================================================


class TestComputeParetoFrontierExtended:
    def test_all_none_metrics_returns_empty(self) -> None:
        trials = [
            _trial(trial_number=1, recall=None, fpr=None),
            _trial(trial_number=2, recall=None, fpr=0.1),
            _trial(trial_number=3, recall=0.5, fpr=None),
        ]
        assert _compute_pareto_frontier(trials) == []

    def test_multiple_non_dominated(self) -> None:
        # Two trials that don't dominate each other:
        # t1: high recall, high FPR
        # t2: lower recall, lower FPR
        t1 = _trial(trial_number=1, recall=0.95, fpr=0.3)
        t2 = _trial(trial_number=2, recall=0.7, fpr=0.05)
        frontier = _compute_pareto_frontier([t1, t2])
        assert len(frontier) == 2

    def test_three_trials_one_dominated(self) -> None:
        t1 = _trial(trial_number=1, recall=0.9, fpr=0.1)
        t2 = _trial(trial_number=2, recall=0.7, fpr=0.2)  # dominated by t1
        t3 = _trial(trial_number=3, recall=0.6, fpr=0.05)
        frontier = _compute_pareto_frontier([t1, t2, t3])
        trial_numbers = {t.trial_number for t in frontier}
        # t2 is dominated: t1 has higher recall AND lower fpr
        assert 2 not in trial_numbers
        assert 1 in trial_numbers
        assert 3 in trial_numbers

    def test_ties_in_recall(self) -> None:
        t1 = _trial(trial_number=1, recall=0.8, fpr=0.2)
        t2 = _trial(trial_number=2, recall=0.8, fpr=0.1)
        frontier = _compute_pareto_frontier([t1, t2])
        # Same recall but t2 has lower FPR. After sorting by recall desc,
        # both have recall=0.8. First one sets best_fpr. Depends on sort stability.
        # t1 and t2 have same recall; both get iterated. First one sets best_fpr,
        # second one only included if fpr <= best_fpr.
        # Since Python sort is stable, original order for ties is preserved.
        # t1 comes first (fpr=0.2 => best_fpr=0.2), then t2 (fpr=0.1 <= 0.2 => included).
        assert len(frontier) == 2

    def test_ties_in_fpr(self) -> None:
        t1 = _trial(trial_number=1, recall=0.9, fpr=0.1)
        t2 = _trial(trial_number=2, recall=0.7, fpr=0.1)
        frontier = _compute_pareto_frontier([t1, t2])
        # Sorted by recall desc: t1 first. best_fpr=0.1.
        # t2: fpr=0.1 <= 0.1 => included (equal is <=).
        assert len(frontier) == 2

    def test_all_identical_trials(self) -> None:
        trials = [_trial(trial_number=i, recall=0.5, fpr=0.2) for i in range(5)]
        frontier = _compute_pareto_frontier(trials)
        # All equal => all included (fpr <= best_fpr at each step since equal)
        assert len(frontier) == 5

    def test_single_trial_on_frontier(self) -> None:
        t = _trial(recall=1.0, fpr=0.0)
        frontier = _compute_pareto_frontier([t])
        assert len(frontier) == 1
        assert frontier[0] is t

    def test_strictly_dominated_chain(self) -> None:
        # t1 dominates t2, t2 dominates t3
        t1 = _trial(trial_number=1, recall=0.9, fpr=0.1)
        t2 = _trial(trial_number=2, recall=0.7, fpr=0.3)
        t3 = _trial(trial_number=3, recall=0.5, fpr=0.5)
        frontier = _compute_pareto_frontier([t3, t1, t2])
        assert len(frontier) == 1
        assert frontier[0].trial_number == 1

    def test_zero_recall_and_fpr(self) -> None:
        t = _trial(recall=0.0, fpr=0.0)
        frontier = _compute_pareto_frontier([t])
        assert len(frontier) == 1


# ===================================================================
# _compute_sensitivity
# ===================================================================


class TestComputeSensitivityExtended:
    def test_empty_specs_no_study(self) -> None:
        result = _compute_sensitivity([], study=None)
        assert result == {}

    def test_multiple_params_no_study_all_zeros(self) -> None:
        specs = [
            ParameterSpec(name="a", param_type="numeric", min_value=0, max_value=1),
            ParameterSpec(name="b", param_type="integer", min_value=0, max_value=10),
        ]
        result = _compute_sensitivity(specs, study=None)
        assert result == {"a": 0.0, "b": 0.0}

    def test_exactly_two_trials_succeeds(self) -> None:
        specs = [
            ParameterSpec(name="x", param_type="numeric", min_value=0.0, max_value=1.0),
        ]
        study = optuna.create_study(direction="maximize")
        for i in range(2):
            trial = study.ask()
            trial.suggest_float("x", 0.0, 1.0)
            study.tell(trial, float(i))
        result = _compute_sensitivity(specs, study)
        # Should have a value for "x" and not be the zeros fallback
        assert "x" in result

    def test_one_trial_returns_zeros(self) -> None:
        specs = [
            ParameterSpec(name="x", param_type="numeric", min_value=0.0, max_value=1.0),
        ]
        study = optuna.create_study(direction="maximize")
        trial = study.ask()
        trial.suggest_float("x", 0.0, 1.0)
        study.tell(trial, 0.5)
        result = _compute_sensitivity(specs, study)
        assert result == {"x": 0.0}

    def test_missing_param_in_evaluator_returns_zero(self) -> None:
        """If a param is in specs but evaluator omits it, we fill in 0.0."""
        specs = [
            ParameterSpec(
                name="x", param_type="numeric", min_value=0.0, max_value=10.0
            ),
            ParameterSpec(
                name="y_unused", param_type="numeric", min_value=0.0, max_value=1.0
            ),
        ]
        study = optuna.create_study(direction="maximize")
        for i in range(10):
            trial = study.ask()
            trial.suggest_float("x", 0.0, 10.0)
            # y_unused is in specs but never suggested => evaluator may omit it
            study.tell(trial, float(i) / 10)
        result = _compute_sensitivity(specs, study)
        assert "x" in result
        # y_unused should be present (filled with 0.0 or actual value)
        assert "y_unused" in result

    def test_all_failed_trials_returns_zeros(self) -> None:
        specs = [
            ParameterSpec(name="x", param_type="numeric", min_value=0.0, max_value=1.0),
        ]
        study = optuna.create_study(direction="maximize")
        for _ in range(5):
            trial = study.ask()
            trial.suggest_float("x", 0.0, 1.0)
            study.tell(trial, state=optuna.trial.TrialState.FAIL)
        result = _compute_sensitivity(specs, study)
        assert result == {"x": 0.0}


# ===================================================================
# _trial_to_json
# ===================================================================


class TestTrialToJson:
    def test_basic_serialization(self) -> None:
        t = TrialResult(
            trial_number=3,
            parameters={"fc": 2.5},
            score=0.87654,
            recall=0.91234,
            false_positive_rate=0.05678,
            result_count=150,
            positive_hits=9,
            negative_hits=1,
            total_positives=10,
            total_negatives=8,
        )
        j = _trial_to_json(t)
        assert j["trialNumber"] == 3
        assert j["parameters"] == {"fc": 2.5}
        assert j["score"] == round(0.87654, 4)
        assert j["recall"] == round(0.91234, 4)
        assert j["falsePositiveRate"] == round(0.05678, 4)
        assert j["resultCount"] == 150
        assert j["positiveHits"] == 9
        assert j["negativeHits"] == 1
        assert j["totalPositives"] == 10
        assert j["totalNegatives"] == 8

    def test_none_values(self) -> None:
        t = TrialResult(
            trial_number=1,
            parameters={},
            score=0.5,
            recall=None,
            false_positive_rate=None,
            result_count=None,
            positive_hits=None,
            negative_hits=None,
        )
        j = _trial_to_json(t)
        assert j["recall"] is None
        assert j["falsePositiveRate"] is None
        assert j["resultCount"] is None
        assert j["positiveHits"] is None
        assert j["negativeHits"] is None

    def test_parameters_is_a_copy(self) -> None:
        original = {"fc": 4.0}
        t = _trial(parameters=original)
        j = _trial_to_json(t)
        assert j["parameters"] is not original
        assert j["parameters"] == original

    def test_score_rounding(self) -> None:
        t = _trial(score=0.123456789)
        j = _trial_to_json(t)
        assert j["score"] == 0.1235

    def test_recall_rounding(self) -> None:
        t = _trial(recall=0.999999)
        j = _trial_to_json(t)
        assert j["recall"] == 1.0


# ===================================================================
# result_to_json
# ===================================================================


class TestResultToJsonExtended:
    def test_error_status_with_message(self) -> None:
        result = OptimizationResult(
            optimization_id="opt_err",
            best_trial=None,
            all_trials=[],
            pareto_frontier=[],
            sensitivity={},
            total_time_seconds=0.123,
            status="error",
            error_message="Something broke",
        )
        j = result_to_json(result)
        assert j["status"] == "error"
        assert j["errorMessage"] == "Something broke"
        assert j["bestTrial"] is None
        assert j["totalTrials"] == 0
        assert j["totalTimeSeconds"] == 0.12

    def test_cancelled_status(self) -> None:
        t = _trial(score=0.5)
        result = OptimizationResult(
            optimization_id="opt_cancel",
            best_trial=t,
            all_trials=[t],
            pareto_frontier=[],
            sensitivity={"x": 0.3},
            total_time_seconds=3.456,
            status="cancelled",
        )
        j = result_to_json(result)
        assert j["status"] == "cancelled"
        assert j["totalTrials"] == 1
        assert j["totalTimeSeconds"] == 3.46

    def test_all_fields_present(self) -> None:
        t = _trial(score=0.9, recall=0.95, fpr=0.05)
        result = OptimizationResult(
            optimization_id="opt_ok",
            best_trial=t,
            all_trials=[t],
            pareto_frontier=[t],
            sensitivity={"x": 0.8},
            total_time_seconds=10.0,
            status="completed",
        )
        j = result_to_json(result)
        expected_keys = {
            "optimizationId",
            "status",
            "bestTrial",
            "allTrials",
            "paretoFrontier",
            "sensitivity",
            "totalTimeSeconds",
            "totalTrials",
            "errorMessage",
        }
        assert set(j.keys()) == expected_keys

    def test_multiple_trials(self) -> None:
        trials = [_trial(trial_number=i, score=i / 5) for i in range(1, 6)]
        result = OptimizationResult(
            optimization_id="opt_multi",
            best_trial=trials[-1],
            all_trials=trials,
            pareto_frontier=trials[:2],
            sensitivity={},
            total_time_seconds=5.0,
            status="completed",
        )
        j = result_to_json(result)
        assert j["totalTrials"] == 5
        assert len(j["allTrials"]) == 5
        assert len(j["paretoFrontier"]) == 2


# ===================================================================
# Config defaults and validation
# ===================================================================


class TestOptimizationConfig:
    def test_defaults(self) -> None:
        cfg = OptimizationConfig()
        assert cfg.budget == 30
        assert cfg.objective == "f1"
        assert cfg.beta == 1.0
        assert cfg.recall_weight == 1.0
        assert cfg.precision_weight == 1.0
        assert cfg.method == "bayesian"
        assert cfg.result_count_penalty == 0.0

    def test_mutable(self) -> None:
        cfg = OptimizationConfig()
        cfg.budget = 50
        assert cfg.budget == 50

    def test_custom_values(self) -> None:
        cfg = OptimizationConfig(
            budget=10,
            objective="mcc",
            method="grid",
            result_count_penalty=0.5,
        )
        assert cfg.budget == 10
        assert cfg.objective == "mcc"
        assert cfg.method == "grid"
        assert cfg.result_count_penalty == 0.5


class TestParameterSpec:
    def test_numeric_defaults(self) -> None:
        spec = ParameterSpec(name="x", param_type="numeric")
        assert spec.min_value is None
        assert spec.max_value is None
        assert spec.log_scale is False
        assert spec.step is None
        assert spec.choices is None

    def test_frozen(self) -> None:
        spec = ParameterSpec(name="x", param_type="numeric", min_value=0.0)
        with pytest.raises(AttributeError):
            spec.name = "y"  # type: ignore[misc]

    def test_categorical(self) -> None:
        spec = ParameterSpec(
            name="direction",
            param_type="categorical",
            choices=["up", "down"],
        )
        assert spec.choices == ["up", "down"]
        assert spec.param_type == "categorical"

    def test_integer_with_step(self) -> None:
        spec = ParameterSpec(
            name="count",
            param_type="integer",
            min_value=0,
            max_value=100,
            step=5,
        )
        assert spec.step == 5


class TestTrialResultDataclass:
    def test_frozen(self) -> None:
        t = _trial()
        with pytest.raises(AttributeError):
            t.score = 1.0  # type: ignore[misc]

    def test_defaults(self) -> None:
        t = TrialResult(
            trial_number=1,
            parameters={},
            score=0.5,
            recall=0.8,
            false_positive_rate=0.1,
            result_count=100,
        )
        assert t.positive_hits is None
        assert t.negative_hits is None
        assert t.total_positives is None
        assert t.total_negatives is None


class TestOptimizationResult:
    def test_mutable(self) -> None:
        result = OptimizationResult(
            optimization_id="x",
            best_trial=None,
            all_trials=[],
            pareto_frontier=[],
            sensitivity={},
            total_time_seconds=0,
            status="running",
        )
        result.status = "completed"
        assert result.status == "completed"

    def test_error_message_default_none(self) -> None:
        result = OptimizationResult(
            optimization_id="x",
            best_trial=None,
            all_trials=[],
            pareto_frontier=[],
            sensitivity={},
            total_time_seconds=0,
            status="completed",
        )
        assert result.error_message is None


# ===================================================================
# _create_sampler
# ===================================================================


class TestCreateSampler:
    def test_bayesian_returns_tpe(self) -> None:
        cfg = OptimizationConfig(method="bayesian")
        specs = [
            ParameterSpec(name="x", param_type="numeric", min_value=0, max_value=1)
        ]
        sampler, budget = _create_sampler(cfg, specs, 20)
        assert isinstance(sampler, optuna.samplers.TPESampler)
        assert budget == 20

    def test_random_returns_random_sampler(self) -> None:
        cfg = OptimizationConfig(method="random")
        specs = [
            ParameterSpec(name="x", param_type="numeric", min_value=0, max_value=1)
        ]
        sampler, budget = _create_sampler(cfg, specs, 15)
        assert isinstance(sampler, optuna.samplers.RandomSampler)
        assert budget == 15

    def test_grid_returns_grid_sampler(self) -> None:
        cfg = OptimizationConfig(method="grid")
        specs = [
            ParameterSpec(name="x", param_type="numeric", min_value=0, max_value=1)
        ]
        sampler, _budget = _create_sampler(cfg, specs, 50)
        assert isinstance(sampler, optuna.samplers.GridSampler)

    def test_grid_budget_capped_by_combinations(self) -> None:
        cfg = OptimizationConfig(method="grid")
        # Categorical with 3 choices => 3 combos, requested budget=100
        specs = [
            ParameterSpec(name="dir", param_type="categorical", choices=["a", "b", "c"])
        ]
        _, budget = _create_sampler(cfg, specs, 100)
        assert budget == 3

    def test_grid_integer_step_default(self) -> None:
        cfg = OptimizationConfig(method="grid")
        # Integer range 0-10 with no step => step = max(1, (10-0)//10) = 1
        # => values = range(0, 11, 1) = 11 values
        specs = [
            ParameterSpec(name="n", param_type="integer", min_value=0, max_value=10)
        ]
        _, budget = _create_sampler(cfg, specs, 50)
        assert budget == 11

    def test_grid_integer_custom_step(self) -> None:
        cfg = OptimizationConfig(method="grid")
        # Integer range 0-10 with step=5 => values = [0, 5, 10] = 3
        specs = [
            ParameterSpec(
                name="n", param_type="integer", min_value=0, max_value=10, step=5
            )
        ]
        _, budget = _create_sampler(cfg, specs, 50)
        assert budget == 3

    def test_grid_numeric_levels_capped_by_budget(self) -> None:
        cfg = OptimizationConfig(method="grid")
        specs = [
            ParameterSpec(name="x", param_type="numeric", min_value=0, max_value=1)
        ]
        # budget=5 => n_levels = min(10, 5) = 5 => 5 combos
        _, budget = _create_sampler(cfg, specs, 5)
        assert budget == 5

    def test_grid_multiple_params_product(self) -> None:
        cfg = OptimizationConfig(method="grid")
        specs = [
            ParameterSpec(name="dir", param_type="categorical", choices=["a", "b"]),
            ParameterSpec(
                name="n", param_type="integer", min_value=0, max_value=4, step=2
            ),
        ]
        # dir: 2 choices, n: [0, 2, 4] = 3 values => 6 combos
        _, budget = _create_sampler(cfg, specs, 100)
        assert budget == 6

    def test_grid_numeric_none_bounds_default(self) -> None:
        cfg = OptimizationConfig(method="grid")
        specs = [ParameterSpec(name="x", param_type="numeric")]
        # min_value=None => 0.0, max_value=None => 1.0
        sampler, budget = _create_sampler(cfg, specs, 20)
        assert isinstance(sampler, optuna.samplers.GridSampler)
        # n_levels = min(10, 20) = 10
        assert budget == 10

    def test_grid_integer_none_bounds_default(self) -> None:
        cfg = OptimizationConfig(method="grid")
        specs = [ParameterSpec(name="n", param_type="integer")]
        # min_value=None => 0, max_value=None => 10
        _, budget = _create_sampler(cfg, specs, 50)
        assert budget == 11  # range(0, 11, 1)

    def test_unknown_method_falls_back_to_tpe(self) -> None:
        cfg = OptimizationConfig()
        object.__setattr__(cfg, "method", "nonexistent")
        specs = [
            ParameterSpec(name="x", param_type="numeric", min_value=0, max_value=1)
        ]
        sampler, budget = _create_sampler(cfg, specs, 10)
        assert isinstance(sampler, optuna.samplers.TPESampler)
        assert budget == 10


# ===================================================================
# _suggest_trial_params
# ===================================================================


class TestSuggestTrialParams:
    def test_numeric_param(self) -> None:
        study = optuna.create_study(direction="maximize")
        ot = study.ask()
        specs = [
            ParameterSpec(name="x", param_type="numeric", min_value=1.0, max_value=10.0)
        ]
        params = _suggest_trial_params(ot, specs)
        assert "x" in params
        x = float(params["x"])
        assert 1.0 <= x <= 10.0

    def test_integer_param(self) -> None:
        study = optuna.create_study(direction="maximize")
        ot = study.ask()
        specs = [
            ParameterSpec(
                name="n", param_type="integer", min_value=5, max_value=50, step=5
            )
        ]
        params = _suggest_trial_params(ot, specs)
        assert "n" in params
        assert isinstance(params["n"], int)
        n = int(params["n"])
        assert 5 <= n <= 50
        assert n % 5 == 0

    def test_categorical_param(self) -> None:
        study = optuna.create_study(direction="maximize")
        ot = study.ask()
        specs = [
            ParameterSpec(name="dir", param_type="categorical", choices=["up", "down"])
        ]
        params = _suggest_trial_params(ot, specs)
        assert params["dir"] in ("up", "down")

    def test_multiple_params(self) -> None:
        study = optuna.create_study(direction="maximize")
        ot = study.ask()
        specs = [
            ParameterSpec(name="x", param_type="numeric", min_value=0, max_value=1),
            ParameterSpec(name="n", param_type="integer", min_value=0, max_value=10),
            ParameterSpec(name="c", param_type="categorical", choices=["a", "b", "c"]),
        ]
        params = _suggest_trial_params(ot, specs)
        assert len(params) == 3
        assert "x" in params
        assert "n" in params
        assert "c" in params

    def test_numeric_none_bounds_default(self) -> None:
        study = optuna.create_study(direction="maximize")
        ot = study.ask()
        specs = [ParameterSpec(name="x", param_type="numeric")]
        params = _suggest_trial_params(ot, specs)
        x = float(params["x"])
        assert 0.0 <= x <= 1.0

    def test_integer_none_bounds_default(self) -> None:
        study = optuna.create_study(direction="maximize")
        ot = study.ask()
        specs = [ParameterSpec(name="n", param_type="integer")]
        params = _suggest_trial_params(ot, specs)
        n = int(params["n"])
        assert 0 <= n <= 100

    def test_categorical_none_choices_uses_empty_string(self) -> None:
        study = optuna.create_study(direction="maximize")
        ot = study.ask()
        specs = [ParameterSpec(name="c", param_type="categorical")]
        params = _suggest_trial_params(ot, specs)
        assert params["c"] == ""

    def test_log_scale_numeric(self) -> None:
        study = optuna.create_study(direction="maximize")
        ot = study.ask()
        specs = [
            ParameterSpec(
                name="lr",
                param_type="numeric",
                min_value=1e-5,
                max_value=1.0,
                log_scale=True,
            )
        ]
        params = _suggest_trial_params(ot, specs)
        lr = float(params["lr"])
        assert 1e-5 <= lr <= 1.0

    def test_empty_parameter_space(self) -> None:
        study = optuna.create_study(direction="maximize")
        ot = study.ask()
        params = _suggest_trial_params(ot, [])
        assert params == {}


# ===================================================================
# Callback functions
# ===================================================================


class TestCallbacks:
    @pytest.mark.asyncio
    async def test_emit_started_payload(self) -> None:
        events: list[JSONObject] = []

        async def capture(event: JSONObject) -> None:
            events.append(event)

        await emit_started(
            capture,
            OptimizationStartedEvent(
                optimization_id="opt_1",
                search_name="GenesByRNASeq",
                record_type="transcript",
                budget=30,
                objective="f1",
                positive_controls_count=10,
                negative_controls_count=5,
                param_space_json=[{"name": "fc", "type": "numeric"}],
            ),
        )

        assert len(events) == 1
        evt = events[0]
        assert evt["type"] == "optimization_progress"
        data = evt["data"]
        assert isinstance(data, dict)
        assert data["status"] == "started"
        assert data["optimizationId"] == "opt_1"
        assert data["searchName"] == "GenesByRNASeq"
        assert data["recordType"] == "transcript"
        assert data["budget"] == 30
        assert data["objective"] == "f1"
        assert data["positiveControlsCount"] == 10
        assert data["negativeControlsCount"] == 5
        assert data["currentTrial"] == 0
        assert data["totalTrials"] == 30
        assert data["bestTrial"] is None
        assert data["recentTrials"] == []
        assert data["parameterSpace"] == [{"name": "fc", "type": "numeric"}]

    @pytest.mark.asyncio
    async def test_emit_trial_progress_payload(self) -> None:
        events: list[JSONObject] = []

        async def capture(event: JSONObject) -> None:
            events.append(event)

        best = _trial(trial_number=1, score=0.9, recall=0.95, fpr=0.05)
        recent = [best, _trial(trial_number=2, score=0.7)]

        await emit_trial_progress(
            capture,
            TrialProgressEvent(
                optimization_id="opt_1",
                trial_num=2,
                budget=30,
                trial_json=_trial_to_json(_trial(trial_number=2, score=0.7)),
                best_trial=best,
                recent_trials=recent,
            ),
        )

        assert len(events) == 1
        data = events[0]["data"]
        assert isinstance(data, dict)
        assert data["status"] == "running"
        assert data["currentTrial"] == 2
        assert data["totalTrials"] == 30
        trial_data = data["trial"]
        assert isinstance(trial_data, dict)
        assert trial_data["trialNumber"] == 2
        best_data = data["bestTrial"]
        assert isinstance(best_data, dict)
        assert best_data["trialNumber"] == 1
        recent = data["recentTrials"]
        assert isinstance(recent, list)
        assert len(recent) == 2

    @pytest.mark.asyncio
    async def test_emit_trial_progress_no_best(self) -> None:
        events: list[JSONObject] = []

        async def capture(event: JSONObject) -> None:
            events.append(event)

        await emit_trial_progress(
            capture,
            TrialProgressEvent(
                optimization_id="opt_1",
                trial_num=1,
                budget=10,
                trial_json={"trialNumber": 1},
                best_trial=None,
                recent_trials=[],
            ),
        )

        data = events[0]["data"]
        assert isinstance(data, dict)
        assert data["bestTrial"] is None
        assert data["recentTrials"] == []

    @pytest.mark.asyncio
    async def test_emit_error_payload(self) -> None:
        events: list[JSONObject] = []

        async def capture(event: JSONObject) -> None:
            events.append(event)

        await emit_error(
            capture,
            optimization_id="opt_err",
            error="WDK is down",
        )

        assert len(events) == 1
        data = events[0]["data"]
        assert isinstance(data, dict)
        assert data["status"] == "error"
        assert data["error"] == "WDK is down"
        assert data["optimizationId"] == "opt_err"

    @pytest.mark.asyncio
    async def test_emit_completed_payload(self) -> None:
        events: list[JSONObject] = []

        async def capture(event: JSONObject) -> None:
            events.append(event)

        t = _trial(score=0.9, recall=0.95, fpr=0.05)

        await emit_completed(
            capture,
            OptimizationCompletedEvent(
                optimization_id="opt_done",
                status="completed",
                budget=30,
                trials=[t],
                best_trial=t,
                pareto=[t],
                sensitivity={"fc": 0.8},
                elapsed=12.345,
            ),
        )

        assert len(events) == 1
        data = events[0]["data"]
        assert isinstance(data, dict)
        assert data["status"] == "completed"
        assert data["optimizationId"] == "opt_done"
        assert data["currentTrial"] == 1
        assert data["totalTrials"] == 30
        best = data["bestTrial"]
        assert isinstance(best, dict)
        assert best["score"] == 0.9
        all_trials = data["allTrials"]
        assert isinstance(all_trials, list)
        assert len(all_trials) == 1
        pareto = data["paretoFrontier"]
        assert isinstance(pareto, list)
        assert len(pareto) == 1
        assert data["sensitivity"] == {"fc": 0.8}
        assert data["totalTimeSeconds"] == 12.35

    @pytest.mark.asyncio
    async def test_emit_completed_no_best_trial(self) -> None:
        events: list[JSONObject] = []

        async def capture(event: JSONObject) -> None:
            events.append(event)

        await emit_completed(
            capture,
            OptimizationCompletedEvent(
                optimization_id="opt_none",
                status="error",
                budget=10,
                trials=[],
                best_trial=None,
                pareto=[],
                sensitivity={},
                elapsed=0.5,
            ),
        )

        data = events[0]["data"]
        assert isinstance(data, dict)
        assert data["bestTrial"] is None
        assert data["allTrials"] == []
        assert data["paretoFrontier"] == []


# ===================================================================
# Integration tests for optimize_search_parameters
# ===================================================================


class TestOptimizeSearchParametersExtended:
    """Additional integration tests beyond the existing test file."""

    @pytest.mark.asyncio
    async def test_bayesian_method(self) -> None:
        mock_wdk = AsyncMock(
            return_value=_make_wdk_result(pos_recall=0.7, neg_fpr=0.15)
        )
        specs = [
            ParameterSpec(
                name="fc", param_type="numeric", min_value=1.0, max_value=16.0
            )
        ]
        cfg = OptimizationConfig(budget=5, objective="f1", method="bayesian")

        with patch(WDK_PATCH, mock_wdk):
            result = await optimize_search_parameters(
                _common_inp(specs),
                config=cfg,
            )

        assert result.status == "completed"
        assert result.best_trial is not None
        assert len(result.all_trials) == 5

    @pytest.mark.asyncio
    async def test_multiple_parameter_types(self) -> None:
        mock_wdk = AsyncMock(return_value=_make_wdk_result(pos_recall=0.8, neg_fpr=0.1))
        specs = [
            ParameterSpec(
                name="fc", param_type="numeric", min_value=1.0, max_value=16.0
            ),
            ParameterSpec(
                name="min_reads",
                param_type="integer",
                min_value=5,
                max_value=50,
                step=5,
            ),
            ParameterSpec(
                name="direction",
                param_type="categorical",
                choices=["up", "down", "both"],
            ),
        ]
        cfg = OptimizationConfig(budget=3, objective="f1", method="random")

        with patch(WDK_PATCH, mock_wdk):
            result = await optimize_search_parameters(
                _common_inp(specs),
                config=cfg,
            )

        assert result.status == "completed"
        for t in result.all_trials:
            assert "fc" in t.parameters
            assert "min_reads" in t.parameters
            assert "direction" in t.parameters

    @pytest.mark.asyncio
    async def test_fixed_parameters_with_empty_values_filtered(self) -> None:
        """Fixed params with empty string or None values should be filtered out."""
        mock_wdk = AsyncMock(return_value=_make_wdk_result(pos_recall=0.8, neg_fpr=0.1))
        specs = [
            ParameterSpec(
                name="fc", param_type="numeric", min_value=1.0, max_value=16.0
            ),
        ]
        cfg = OptimizationConfig(budget=1, objective="f1", method="random")

        with patch(WDK_PATCH, mock_wdk):
            await optimize_search_parameters(
                _common_inp(
                    specs,
                    fixed_parameters=cast(
                        "JSONObject",
                        {"organism": "P. falciparum", "empty": "", "null_val": None},
                    ),
                ),
                config=cfg,
            )

        # run_positive_negative_controls takes IntersectionConfig as first positional arg
        call_config = mock_wdk.call_args.args[0]
        target_params = call_config.target_parameters
        assert "organism" in target_params
        assert "empty" not in target_params
        assert "null_val" not in target_params

    @pytest.mark.asyncio
    async def test_optimization_id_format(self) -> None:
        mock_wdk = AsyncMock(return_value=_make_wdk_result(pos_recall=0.8, neg_fpr=0.1))
        specs = [
            ParameterSpec(
                name="fc", param_type="numeric", min_value=1.0, max_value=16.0
            ),
        ]
        cfg = OptimizationConfig(budget=1, objective="f1", method="random")

        with patch(WDK_PATCH, mock_wdk):
            result = await optimize_search_parameters(
                _common_inp(specs),
                config=cfg,
            )

        assert result.optimization_id.startswith("opt_")
        # The numeric part should be parseable as an integer
        numeric_part = result.optimization_id[4:]
        assert numeric_part.isdigit()

    @pytest.mark.asyncio
    async def test_no_progress_callback_works(self) -> None:
        mock_wdk = AsyncMock(return_value=_make_wdk_result(pos_recall=0.8, neg_fpr=0.1))
        specs = [
            ParameterSpec(
                name="fc", param_type="numeric", min_value=1.0, max_value=16.0
            ),
        ]
        cfg = OptimizationConfig(budget=2, objective="f1", method="random")

        with patch(WDK_PATCH, mock_wdk):
            result = await optimize_search_parameters(
                _common_inp(specs),
                config=cfg,
                progress_callback=None,
            )

        assert result.status == "completed"
        assert result.best_trial is not None

    @pytest.mark.asyncio
    async def test_sensitivity_populated(self) -> None:
        """Sensitivity dict should have keys for each param in the space."""
        mock_wdk = AsyncMock(return_value=_make_wdk_result(pos_recall=0.7, neg_fpr=0.2))
        specs = [
            ParameterSpec(
                name="fc", param_type="numeric", min_value=1.0, max_value=16.0
            ),
            ParameterSpec(name="n", param_type="integer", min_value=0, max_value=10),
        ]
        cfg = OptimizationConfig(budget=5, objective="f1", method="random")

        with patch(WDK_PATCH, mock_wdk):
            result = await optimize_search_parameters(
                _common_inp(specs),
                config=cfg,
            )

        assert "fc" in result.sensitivity
        assert "n" in result.sensitivity

    @pytest.mark.asyncio
    async def test_pareto_frontier_populated(self) -> None:
        # neg_fpr=0.5 ensures int(8*0.5)=4 > 0 so falsePositiveRate is not None
        mock_wdk = AsyncMock(return_value=_make_wdk_result(pos_recall=0.8, neg_fpr=0.5))
        specs = [
            ParameterSpec(
                name="fc", param_type="numeric", min_value=1.0, max_value=16.0
            ),
        ]
        cfg = OptimizationConfig(budget=3, objective="f1", method="random")

        with patch(WDK_PATCH, mock_wdk):
            result = await optimize_search_parameters(
                _common_inp(specs),
                config=cfg,
            )

        # All trials return the same result => all on pareto frontier
        assert len(result.pareto_frontier) >= 1

    @pytest.mark.asyncio
    async def test_total_time_seconds_populated(self) -> None:
        mock_wdk = AsyncMock(return_value=_make_wdk_result(pos_recall=0.8, neg_fpr=0.1))
        specs = [
            ParameterSpec(
                name="fc", param_type="numeric", min_value=1.0, max_value=16.0
            ),
        ]
        cfg = OptimizationConfig(budget=1, objective="f1", method="random")

        with patch(WDK_PATCH, mock_wdk):
            result = await optimize_search_parameters(
                _common_inp(specs),
                config=cfg,
            )

        assert result.total_time_seconds >= 0

    @pytest.mark.asyncio
    async def test_different_objectives_produce_different_scores(self) -> None:
        """Different objectives on the same WDK result should yield different scores."""
        wdk_result = _make_wdk_result(pos_recall=0.7, neg_fpr=0.3)
        specs = [
            ParameterSpec(
                name="fc", param_type="numeric", min_value=1.0, max_value=16.0
            ),
        ]

        scores: dict[str, float] = {}
        for objective in [
            "recall",
            "precision",
            "f1",
            "balanced_accuracy",
            "youdens_j",
        ]:
            cfg = OptimizationConfig(budget=1, objective=objective, method="random")
            with patch(WDK_PATCH, AsyncMock(return_value=wdk_result)):
                result = await optimize_search_parameters(
                    _common_inp(specs),
                    config=cfg,
                )
            if result.best_trial:
                scores[objective] = result.best_trial.score

        # recall=0.7 vs precision/specificity=0.7 vs f1 vs balanced_accuracy vs youdens_j
        # At least some should be distinct
        unique_scores = {round(s, 4) for s in scores.values()}
        assert len(unique_scores) >= 2, f"Expected distinct scores, got {scores}"

    @pytest.mark.asyncio
    async def test_wdk_result_with_no_positive_data(self) -> None:
        """WDK result missing positive/negative data should still produce a trial."""
        wdk_result: JSONObject = {
            "target": {"resultCount": 50},
            "positive": None,
            "negative": None,
        }
        mock_wdk = AsyncMock(return_value=wdk_result)
        specs = [
            ParameterSpec(
                name="fc", param_type="numeric", min_value=1.0, max_value=16.0
            ),
        ]
        cfg = OptimizationConfig(budget=1, objective="f1", method="random")

        with patch(WDK_PATCH, mock_wdk):
            result = await optimize_search_parameters(
                _common_inp(specs),
                config=cfg,
            )

        assert result.status == "completed"
        assert len(result.all_trials) == 1
        # recall and fpr should be None => score=0
        assert result.all_trials[0].recall is None
        assert result.all_trials[0].false_positive_rate is None

    @pytest.mark.asyncio
    async def test_cache_prevents_duplicate_wdk_calls(self) -> None:
        """Identical param combos should be served from cache, not re-evaluated."""
        call_count = 0

        async def counting_wdk(*args: Any, **kwargs: Any) -> JSONObject:
            nonlocal call_count
            call_count += 1
            return _make_wdk_result(pos_recall=0.8, neg_fpr=0.1)

        # Use grid search with a single categorical value => all trials identical
        specs = [
            ParameterSpec(name="dir", param_type="categorical", choices=["up"]),
        ]
        cfg = OptimizationConfig(budget=5, objective="f1", method="random")

        with patch(WDK_PATCH, counting_wdk):
            result = await optimize_search_parameters(
                _common_inp(specs),
                config=cfg,
            )

        # All 5 trials have the same params => only 1 WDK call
        assert call_count == 1
        assert result.status == "completed"

    @pytest.mark.asyncio
    async def test_error_emit_on_early_abort(self) -> None:
        """Early abort due to consecutive failures should emit error event."""
        mock_wdk = AsyncMock(side_effect=RuntimeError("always fail"))
        specs = [
            ParameterSpec(
                name="fc", param_type="numeric", min_value=1.0, max_value=16.0
            ),
        ]
        cfg = OptimizationConfig(budget=40, objective="f1", method="random")
        events: list[JSONObject] = []

        async def capture(event: JSONObject) -> None:
            events.append(event)

        with patch(WDK_PATCH, mock_wdk):
            result = await optimize_search_parameters(
                _common_inp(specs),
                config=cfg,
                progress_callback=capture,
            )

        assert result.status == "error"
        # Should have: started + some running + error
        statuses = []
        for e in events:
            d = e.get("data")
            if isinstance(d, dict):
                statuses.append(d.get("status"))
        assert "started" in statuses
        assert "error" in statuses

    @pytest.mark.asyncio
    async def test_completed_event_not_emitted_on_error(self) -> None:
        """When status is 'error', the completed callback should NOT fire."""
        mock_wdk = AsyncMock(side_effect=RuntimeError("always fail"))
        specs = [
            ParameterSpec(
                name="fc", param_type="numeric", min_value=1.0, max_value=16.0
            ),
        ]
        cfg = OptimizationConfig(budget=40, objective="f1", method="random")
        events: list[JSONObject] = []

        async def capture(event: JSONObject) -> None:
            events.append(event)

        with patch(WDK_PATCH, mock_wdk):
            result = await optimize_search_parameters(
                _common_inp(specs),
                config=cfg,
                progress_callback=capture,
            )

        assert result.status == "error"
        # The "completed" status should not appear in events
        statuses = []
        for e in events:
            d = e.get("data")
            if isinstance(d, dict):
                statuses.append(d.get("status"))
        assert "completed" not in statuses


# ===================================================================
# Edge cases for scoring with MCC approximation
# ===================================================================


class TestMCCEdgeCases:
    def test_mcc_all_positive_recall_1_fpr_0(self) -> None:
        cfg = OptimizationConfig(objective="mcc")
        # Perfect classifier
        score = _compute_score(1.0, 0.0, cfg)
        assert score == pytest.approx(1.0)

    def test_mcc_all_negative_recall_0_fpr_1(self) -> None:
        cfg = OptimizationConfig(objective="mcc")
        # Worst classifier: misses all positives, flags all negatives
        score = _compute_score(0.0, 1.0, cfg)
        assert score == pytest.approx(-1.0)

    def test_mcc_symmetric_case(self) -> None:
        cfg = OptimizationConfig(objective="mcc")
        # recall=0.8, fpr=0.2 => tpr=0.8, tnr=0.8, fpr=0.2, fnr=0.2
        # num = 0.8*0.8 - 0.2*0.2 = 0.64 - 0.04 = 0.6
        # denom = sqrt(1.0 * 1.0 * 1.0 * 1.0) = 1.0
        score = _compute_score(0.8, 0.2, cfg)
        assert score == pytest.approx(0.6)

    def test_mcc_nearly_zero_denom(self) -> None:
        cfg = OptimizationConfig(objective="mcc")
        # recall=1.0, fpr=1.0 => tpr=1, tnr=0, fpr=1, fnr=0
        # denom = sqrt((1+1)*(1+0)*(0+1)*(0+0)) = sqrt(0) = 0
        score = _compute_score(1.0, 1.0, cfg)
        assert score == 0.0


# ===================================================================
# Grid sampler edge cases
# ===================================================================


class TestGridSamplerEdgeCases:
    def test_grid_single_categorical_value(self) -> None:
        cfg = OptimizationConfig(method="grid")
        specs = [ParameterSpec(name="x", param_type="categorical", choices=["only"])]
        _sampler, budget = _create_sampler(cfg, specs, 100)
        assert budget == 1

    def test_grid_empty_choices_falls_through_to_numeric(self) -> None:
        """Empty choices list is falsy, so the categorical branch is skipped
        and the param is treated as numeric (falling to the else branch).
        This is a quirk of the implementation: ``p.choices`` is [] which is
        falsy, so ``p.param_type == "categorical" and p.choices`` is False.
        """
        cfg = OptimizationConfig(method="grid")
        specs = [ParameterSpec(name="x", param_type="categorical", choices=[])]
        _sampler, budget = _create_sampler(cfg, specs, 100)
        # Falls through to numeric: n_levels=min(10,100)=10, range 0.0-1.0
        assert budget == 10

    def test_grid_budget_one_numeric(self) -> None:
        cfg = OptimizationConfig(method="grid")
        specs = [
            ParameterSpec(name="x", param_type="numeric", min_value=0.0, max_value=1.0)
        ]
        # budget=1 => n_levels=min(10, 1)=1 => step_size = (1-0)/max(0,1) = 1.0
        # grid = [0.0] => 1 combo
        _, budget = _create_sampler(cfg, specs, 1)
        assert budget == 1

    def test_grid_integer_same_min_max(self) -> None:
        cfg = OptimizationConfig(method="grid")
        specs = [
            ParameterSpec(name="n", param_type="integer", min_value=5, max_value=5)
        ]
        # range(5, 6, max(1, 0//10)=1) = [5] => 1 combo
        _, budget = _create_sampler(cfg, specs, 100)
        assert budget == 1
