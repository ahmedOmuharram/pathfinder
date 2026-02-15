"""Tests for veupath_chatbot.services.parameter_optimization.

All WDK calls are mocked — these tests validate the optimisation loop logic,
scoring, error handling, cancellation, and early-abort behaviour.
"""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import AsyncMock, patch

import optuna
import pytest

from veupath_chatbot.platform.types import JSONArray, JSONObject
from veupath_chatbot.services.parameter_optimization import (
    OptimizationConfig,
    OptimizationResult,
    ParameterSpec,
    TrialResult,
    _compute_pareto_frontier,
    _compute_score,
    _compute_sensitivity,
    optimize_search_parameters,
    result_to_json,
)


def _make_wdk_result(
    *,
    result_count: int = 100,
    pos_recall: float = 0.8,
    neg_fpr: float = 0.1,
    positive_controls: list[str] | None = None,
    negative_controls: list[str] | None = None,
) -> JSONObject:
    """Build a realistic ``run_positive_negative_controls`` return value.

    :param result_count: Expected result count (default: 100).
    :param pos_recall: Positive recall target (default: 0.8).
    :param neg_fpr: Negative false positive rate target (default: 0.1).
    :param positive_controls: Positive control IDs (default: None).
    :param negative_controls: Negative control IDs (default: None).

    """
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
            "intersectionIdsSample": cast(JSONArray, pos_found_ids[:50]),
            "intersectionIds": cast(JSONArray, pos_found_ids),
            "missingIdsSample": cast(
                JSONArray, [x for x in pos if x not in pos_found_ids][:50]
            ),
            "recall": n_pos_found / len(pos) if n_pos_found > 0 else None,
        },
        "negative": {
            "controlsCount": len(neg),
            "intersectionCount": n_neg_found,
            "intersectionIdsSample": cast(JSONArray, neg_found_ids[:50]),
            "intersectionIds": cast(JSONArray, neg_found_ids),
            "unexpectedHitsSample": cast(JSONArray, neg_found_ids[:50]),
            "falsePositiveRate": n_neg_found / len(neg) if n_neg_found > 0 else None,
        },
    }


COMMON_KWARGS: dict[str, Any] = {
    "site_id": "plasmodb",
    "record_type": "transcript",
    "search_name": "TestSearch",
    "fixed_parameters": cast(JSONObject, {"organism": "P. falciparum"}),
    "controls_search_name": "GeneByLocusTag",
    "controls_param_name": "ds_gene_ids",
    "positive_controls": [f"POS_{i}" for i in range(10)],
    "negative_controls": [f"NEG_{i}" for i in range(8)],
}


class TestComputeScore:
    def test_f1_perfect(self) -> None:
        cfg = OptimizationConfig(objective="f1")
        score = _compute_score(recall=1.0, fpr=0.0, cfg=cfg)
        assert score == 1.0

    def test_f1_zero_recall(self) -> None:
        cfg = OptimizationConfig(objective="f1")
        score = _compute_score(recall=0.0, fpr=0.0, cfg=cfg)
        assert score == 0.0

    def test_f1_balanced(self) -> None:
        cfg = OptimizationConfig(objective="f1")
        score = _compute_score(recall=0.8, fpr=0.1, cfg=cfg)
        # precision = 1 - 0.1 = 0.9
        # f1 = 2 * 0.9 * 0.8 / (0.9 + 0.8) = 1.44 / 1.7 ≈ 0.847
        assert 0.84 < score < 0.86

    def test_recall_objective(self) -> None:
        cfg = OptimizationConfig(objective="recall")
        score = _compute_score(recall=0.7, fpr=0.5, cfg=cfg)
        assert score == 0.7

    def test_precision_objective(self) -> None:
        cfg = OptimizationConfig(objective="precision")
        score = _compute_score(recall=0.7, fpr=0.3, cfg=cfg)
        assert score == pytest.approx(0.7)  # precision = 1 - 0.3

    def test_none_values_default_to_zero(self) -> None:
        cfg = OptimizationConfig(objective="f1")
        score = _compute_score(recall=None, fpr=None, cfg=cfg)
        assert score == 0.0

    def test_f_beta_with_beta_2(self) -> None:
        cfg = OptimizationConfig(objective="f_beta", beta=2.0)
        score = _compute_score(recall=0.9, fpr=0.2, cfg=cfg)
        # precision = 0.8, beta^2 = 4
        # f_beta = (1+4) * 0.8 * 0.9 / (4*0.8 + 0.9) = 5*0.72/(3.2+0.9) = 3.6/4.1 ≈ 0.878
        assert 0.87 < score < 0.89

    def test_result_count_penalty_zero_weight(self) -> None:
        """No penalty when weight is 0."""
        cfg = OptimizationConfig(objective="f1", result_count_penalty=0.0)
        score_no_penalty = _compute_score(
            recall=0.8, fpr=0.1, cfg=cfg, result_count=5000
        )
        score_baseline = _compute_score(recall=0.8, fpr=0.1, cfg=cfg, result_count=None)
        assert score_no_penalty == score_baseline

    def test_result_count_penalty_applied(self) -> None:
        """Larger result sets should produce lower scores with penalty."""
        cfg = OptimizationConfig(objective="f1", result_count_penalty=0.1)
        score_small = _compute_score(recall=0.8, fpr=0.1, cfg=cfg, result_count=200)
        score_large = _compute_score(recall=0.8, fpr=0.1, cfg=cfg, result_count=5000)
        assert score_small > score_large

    def test_result_count_penalty_floor_at_zero(self) -> None:
        """Score should never go below zero."""
        cfg = OptimizationConfig(objective="f1", result_count_penalty=10.0)
        score = _compute_score(recall=0.1, fpr=0.9, cfg=cfg, result_count=50000)
        assert score == 0.0


class TestComputePareto:
    def test_empty(self) -> None:
        assert _compute_pareto_frontier([]) == []

    def test_single_trial(self) -> None:
        t = TrialResult(
            trial_number=1,
            parameters={},
            score=0.8,
            recall=0.9,
            false_positive_rate=0.1,
            result_count=100,
        )
        frontier = _compute_pareto_frontier([t])
        assert len(frontier) == 1
        assert frontier[0] is t

    def test_dominated_excluded(self) -> None:
        good = TrialResult(
            trial_number=1,
            parameters={},
            score=0.9,
            recall=0.9,
            false_positive_rate=0.1,
            result_count=100,
        )
        bad = TrialResult(
            trial_number=2,
            parameters={},
            score=0.3,
            recall=0.5,
            false_positive_rate=0.5,
            result_count=50,
        )
        frontier = _compute_pareto_frontier([good, bad])
        # good dominates bad (higher recall AND lower FPR)
        assert len(frontier) == 1
        assert frontier[0] is good

    def test_trials_with_none_metrics_excluded(self) -> None:
        """Trials with None recall/fpr should be excluded from Pareto."""
        t = TrialResult(
            trial_number=1,
            parameters={},
            score=0.0,
            recall=None,
            false_positive_rate=None,
            result_count=None,
        )
        assert _compute_pareto_frontier([t]) == []


class TestComputeSensitivity:
    def test_no_study_returns_zeros(self) -> None:
        specs = [
            ParameterSpec(name="x", param_type="numeric", min_value=0.0, max_value=1.0)
        ]
        result = _compute_sensitivity(specs, study=None)
        assert result == {"x": 0.0}

    def test_too_few_completed_trials_returns_zeros(self) -> None:
        specs = [
            ParameterSpec(name="x", param_type="numeric", min_value=0.0, max_value=1.0)
        ]
        study = optuna.create_study(direction="maximize")
        # Add only 1 trial — below the minimum (2) for fANOVA.
        trial = study.ask()
        trial.suggest_float("x", 0.0, 1.0)
        study.tell(trial, 0.5)
        result = _compute_sensitivity(specs, study)
        assert result == {"x": 0.0}

    def test_sensitivity_with_correlated_param(self) -> None:
        """A parameter strongly correlated with score should have high importance."""
        specs = [
            ParameterSpec(name="x", param_type="numeric", min_value=0.0, max_value=10.0)
        ]
        study = optuna.create_study(direction="maximize")
        # x linearly maps to score — fANOVA should give high importance.
        for i in range(1, 11):
            trial = study.ask()
            trial.suggest_float("x", 0.0, 10.0)
            study.tell(trial, float(i) / 10)
        result = _compute_sensitivity(specs, study)
        assert result["x"] > 0.5


class TestResultToJson:
    def test_round_trip(self) -> None:
        trial = TrialResult(
            trial_number=1,
            parameters={"fc": 4.0},
            score=0.85,
            recall=0.9,
            false_positive_rate=0.1,
            result_count=100,
            positive_hits=9,
            negative_hits=1,
            total_positives=10,
            total_negatives=8,
        )
        result = OptimizationResult(
            optimization_id="test_opt",
            best_trial=trial,
            all_trials=[trial],
            pareto_frontier=[trial],
            sensitivity={"fc": 0.7},
            total_time_seconds=5.5,
            status="completed",
        )
        j = result_to_json(result)
        assert j.get("status") == "completed"
        best = j.get("bestTrial")
        assert isinstance(best, dict)
        assert best.get("score") == 0.85
        assert j["totalTrials"] == 1

    def test_none_best_trial(self) -> None:
        result = OptimizationResult(
            optimization_id="test_opt",
            best_trial=None,
            all_trials=[],
            pareto_frontier=[],
            sensitivity={},
            total_time_seconds=1.0,
            status="error",
            error_message="all trials failed",
        )
        j = result_to_json(result)
        assert j["bestTrial"] is None
        assert j["errorMessage"] == "all trials failed"


WDK_PATCH = (
    "veupath_chatbot.services.parameter_optimization.run_positive_negative_controls"
)


class TestOptimizeSearchParameters:
    """Tests for the core optimize_search_parameters function."""

    @pytest.mark.asyncio
    async def test_successful_optimization(self) -> None:
        """All trials succeed → bestTrial should be populated and status 'completed'."""
        mock_wdk = AsyncMock(return_value=_make_wdk_result(pos_recall=0.8, neg_fpr=0.1))
        specs = [
            ParameterSpec(
                name="fold_change", param_type="numeric", min_value=1.0, max_value=16.0
            )
        ]
        cfg = OptimizationConfig(budget=5, objective="f1", method="random")

        with patch(WDK_PATCH, mock_wdk):
            result = await optimize_search_parameters(
                **COMMON_KWARGS,
                parameter_space=specs,
                config=cfg,
            )

        assert result.status == "completed"
        assert result.best_trial is not None
        assert result.best_trial.score > 0
        assert len(result.all_trials) == 5
        assert mock_wdk.call_count == 5

    @pytest.mark.asyncio
    async def test_all_trials_fail_with_exception(self) -> None:
        """All WDK calls raise → status should be 'completed', bestTrial None."""
        mock_wdk = AsyncMock(side_effect=RuntimeError("WDK 422 error"))
        specs = [
            ParameterSpec(
                name="fold_change", param_type="numeric", min_value=1.0, max_value=16.0
            )
        ]
        cfg = OptimizationConfig(budget=5, objective="f1", method="random")

        with patch(WDK_PATCH, mock_wdk):
            result = await optimize_search_parameters(
                **COMMON_KWARGS,
                parameter_space=specs,
                config=cfg,
            )

        assert result.best_trial is None
        assert len(result.all_trials) == 5
        # All trials should have score=0
        for t in result.all_trials:
            assert t.score == 0.0
            assert t.recall is None

    @pytest.mark.asyncio
    async def test_all_trials_fail_with_error_dict(self) -> None:
        """WDK returns error dict → treated as failed trial."""
        mock_wdk = AsyncMock(return_value={"error": "Invalid value 'average'."})
        specs = [
            ParameterSpec(
                name="fold_change", param_type="numeric", min_value=1.0, max_value=16.0
            )
        ]
        cfg = OptimizationConfig(budget=3, objective="f1", method="random")

        with patch(WDK_PATCH, mock_wdk):
            result = await optimize_search_parameters(
                **COMMON_KWARGS,
                parameter_space=specs,
                config=cfg,
            )

        assert result.best_trial is None
        for t in result.all_trials:
            assert t.score == 0.0

    @pytest.mark.asyncio
    async def test_mixed_success_and_failure(self) -> None:
        """Some trials succeed, some fail → bestTrial from successful ones."""
        call_count = 0

        async def _mixed_wdk(**kwargs: Any) -> JSONObject:
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 0:
                raise RuntimeError("WDK error on even trials")
            return _make_wdk_result(pos_recall=0.8, neg_fpr=0.1)

        specs = [
            ParameterSpec(
                name="fold_change", param_type="numeric", min_value=1.0, max_value=16.0
            )
        ]
        cfg = OptimizationConfig(budget=6, objective="f1", method="random")

        with patch(WDK_PATCH, _mixed_wdk):
            result = await optimize_search_parameters(
                **COMMON_KWARGS,
                parameter_space=specs,
                config=cfg,
            )

        assert result.status == "completed"
        assert result.best_trial is not None
        assert result.best_trial.score > 0
        # Some trials should have non-zero scores
        successful = [t for t in result.all_trials if t.score > 0]
        failed = [t for t in result.all_trials if t.score == 0]
        assert len(successful) >= 1
        assert len(failed) >= 1

    @pytest.mark.asyncio
    async def test_cancellation(self) -> None:
        """Cancel after a few trials → status 'cancelled', partial results."""
        call_count = 0

        async def _slow_wdk(**kwargs: Any) -> JSONObject:
            nonlocal call_count
            call_count += 1
            return _make_wdk_result(pos_recall=0.8, neg_fpr=0.1)

        specs = [
            ParameterSpec(
                name="fold_change", param_type="numeric", min_value=1.0, max_value=16.0
            )
        ]
        cfg = OptimizationConfig(budget=20, objective="f1", method="random")
        cancel_after = 3
        trial_count = 0

        def check_cancelled() -> bool:
            return trial_count >= cancel_after

        optimize_search_parameters.__wrapped__ if hasattr(
            optimize_search_parameters, "__wrapped__"
        ) else None

        with patch(WDK_PATCH, _slow_wdk):
            result = await optimize_search_parameters(
                **COMMON_KWARGS,
                parameter_space=specs,
                config=cfg,
                check_cancelled=lambda: call_count >= cancel_after,
            )

        assert result.status == "cancelled"
        assert len(result.all_trials) < 20
        assert len(result.all_trials) >= cancel_after

    @pytest.mark.asyncio
    async def test_progress_callback_called(self) -> None:
        """Progress callback should fire for start, each trial, and completion."""
        mock_wdk = AsyncMock(return_value=_make_wdk_result(pos_recall=0.8, neg_fpr=0.1))
        specs = [
            ParameterSpec(
                name="fold_change", param_type="numeric", min_value=1.0, max_value=16.0
            )
        ]
        cfg = OptimizationConfig(budget=3, objective="f1", method="random")

        events: list[JSONObject] = []

        async def capture_event(event: JSONObject) -> None:
            events.append(event)

        with patch(WDK_PATCH, mock_wdk):
            await optimize_search_parameters(
                **COMMON_KWARGS,
                parameter_space=specs,
                config=cfg,
                progress_callback=capture_event,
            )

        assert len(events) >= 5  # 1 start + 3 trials + 1 completion
        statuses = [
            (data if isinstance((data := e.get("data")), dict) else {}).get("status")
            for e in events
        ]
        assert statuses[0] == "started"
        assert statuses[-1] == "completed"
        assert all(s == "running" for s in statuses[1:-1])

    @pytest.mark.asyncio
    async def test_progress_callback_for_failed_trials(self) -> None:
        """Failed trials should still emit progress events."""
        mock_wdk = AsyncMock(side_effect=RuntimeError("fail"))
        specs = [
            ParameterSpec(
                name="fold_change", param_type="numeric", min_value=1.0, max_value=16.0
            )
        ]
        cfg = OptimizationConfig(budget=3, objective="f1", method="random")

        events: list[JSONObject] = []

        async def capture_event(event: JSONObject) -> None:
            events.append(event)

        with patch(WDK_PATCH, mock_wdk):
            await optimize_search_parameters(
                **COMMON_KWARGS,
                parameter_space=specs,
                config=cfg,
                progress_callback=capture_event,
            )

        # Should have: 1 start + 3 failed trials + 1 completion = 5 events
        assert len(events) == 5

        # Failed trial events should have error info
        def _status(ev: JSONObject) -> str | None:
            d = ev.get("data")
            if not isinstance(d, dict):
                return None
            s = d.get("status")
            return str(s) if isinstance(s, str) else None

        trial_events = [e for e in events if _status(e) == "running"]
        assert len(trial_events) == 3

    @pytest.mark.asyncio
    async def test_integer_parameter(self) -> None:
        """Integer parameters should use suggest_int."""
        mock_wdk = AsyncMock(return_value=_make_wdk_result(pos_recall=0.7, neg_fpr=0.2))
        specs = [
            ParameterSpec(
                name="min_reads",
                param_type="integer",
                min_value=5,
                max_value=50,
                step=5,
            )
        ]
        cfg = OptimizationConfig(budget=3, objective="f1", method="random")

        with patch(WDK_PATCH, mock_wdk):
            result = await optimize_search_parameters(
                **COMMON_KWARGS,
                parameter_space=specs,
                config=cfg,
            )

        assert result.status == "completed"
        for t in result.all_trials:
            assert isinstance(t.parameters["min_reads"], int)

    @pytest.mark.asyncio
    async def test_categorical_parameter(self) -> None:
        """Categorical parameters should use suggest_categorical."""
        mock_wdk = AsyncMock(return_value=_make_wdk_result(pos_recall=0.7, neg_fpr=0.2))
        specs = [
            ParameterSpec(
                name="direction",
                param_type="categorical",
                choices=["up-regulated", "down-regulated"],
            )
        ]
        cfg = OptimizationConfig(budget=3, objective="f1", method="random")

        with patch(WDK_PATCH, mock_wdk):
            result = await optimize_search_parameters(
                **COMMON_KWARGS,
                parameter_space=specs,
                config=cfg,
            )

        assert result.status == "completed"
        for t in result.all_trials:
            assert t.parameters["direction"] in ("up-regulated", "down-regulated")

    @pytest.mark.asyncio
    async def test_grid_search_method(self) -> None:
        """Grid search should respect the grid and not exceed combos."""
        mock_wdk = AsyncMock(return_value=_make_wdk_result(pos_recall=0.7, neg_fpr=0.2))
        specs = [
            ParameterSpec(
                name="fold_change", param_type="numeric", min_value=1.0, max_value=5.0
            )
        ]
        cfg = OptimizationConfig(budget=50, objective="f1", method="grid")

        with patch(WDK_PATCH, mock_wdk):
            result = await optimize_search_parameters(
                **COMMON_KWARGS,
                parameter_space=specs,
                config=cfg,
            )

        assert result.status == "completed"
        # Grid should create ≤ 10 levels by default (min(10, budget))
        assert len(result.all_trials) <= 10

    @pytest.mark.asyncio
    async def test_failed_trials_include_total_controls(self) -> None:
        """Even failed trials should report total_positives and total_negatives."""
        mock_wdk = AsyncMock(side_effect=RuntimeError("fail"))
        specs = [
            ParameterSpec(
                name="fold_change", param_type="numeric", min_value=1.0, max_value=16.0
            )
        ]
        cfg = OptimizationConfig(budget=2, objective="f1", method="random")

        with patch(WDK_PATCH, mock_wdk):
            result = await optimize_search_parameters(
                **COMMON_KWARGS,
                parameter_space=specs,
                config=cfg,
            )

        for t in result.all_trials:
            assert t.total_positives == 10
            assert t.total_negatives == 8

    @pytest.mark.asyncio
    async def test_early_abort_on_consecutive_failures(self) -> None:
        """Optimization should abort early if many consecutive trials fail."""
        mock_wdk = AsyncMock(side_effect=RuntimeError("always fail"))
        specs = [
            ParameterSpec(
                name="fold_change", param_type="numeric", min_value=1.0, max_value=16.0
            )
        ]
        cfg = OptimizationConfig(budget=40, objective="f1", method="random")

        with patch(WDK_PATCH, mock_wdk):
            result = await optimize_search_parameters(
                **COMMON_KWARGS,
                parameter_space=specs,
                config=cfg,
            )

        # Should abort well before 40 trials
        assert len(result.all_trials) < 40
        assert result.status == "error"
        assert result.error_message is not None

    @pytest.mark.asyncio
    async def test_no_controls_provided(self) -> None:
        """Should work even with no controls (edge case)."""
        mock_wdk = AsyncMock(return_value=_make_wdk_result(pos_recall=0.0, neg_fpr=0.0))
        specs = [
            ParameterSpec(
                name="fold_change", param_type="numeric", min_value=1.0, max_value=16.0
            )
        ]
        cfg = OptimizationConfig(budget=3, objective="f1", method="random")
        kwargs = {**COMMON_KWARGS, "positive_controls": None, "negative_controls": None}

        with patch(WDK_PATCH, mock_wdk):
            result = await optimize_search_parameters(
                **kwargs,
                parameter_space=specs,
                config=cfg,
            )

        assert result.status == "completed"

    @pytest.mark.asyncio
    async def test_early_stop_on_perfect_score(self) -> None:
        """Optimization should stop early when a perfect score is reached."""
        mock_wdk = AsyncMock(return_value=_make_wdk_result(pos_recall=1.0, neg_fpr=0.0))
        specs = [
            ParameterSpec(
                name="fold_change", param_type="numeric", min_value=1.0, max_value=16.0
            )
        ]
        cfg = OptimizationConfig(budget=40, objective="f1", method="random")

        with patch(WDK_PATCH, mock_wdk):
            result = await optimize_search_parameters(
                **COMMON_KWARGS,
                parameter_space=specs,
                config=cfg,
            )

        # Perfect score on first trial → should stop after just 1 trial.
        assert result.status == "completed"
        assert len(result.all_trials) == 1
        assert result.best_trial is not None
        assert result.best_trial.score >= 0.99

    @pytest.mark.asyncio
    async def test_early_stop_on_plateau(self) -> None:
        """Optimization should stop if score doesn't improve for N trials."""
        # All trials return the same mediocre score.
        mock_wdk = AsyncMock(return_value=_make_wdk_result(pos_recall=0.5, neg_fpr=0.3))
        specs = [
            ParameterSpec(
                name="fold_change", param_type="numeric", min_value=1.0, max_value=16.0
            )
        ]
        cfg = OptimizationConfig(budget=40, objective="f1", method="random")

        with patch(WDK_PATCH, mock_wdk):
            result = await optimize_search_parameters(
                **COMMON_KWARGS,
                parameter_space=specs,
                config=cfg,
            )

        # Plateau window = 10: first trial sets best, next 10 don't improve → stop at 11.
        assert result.status == "completed"
        assert len(result.all_trials) <= 12  # 1 initial + 10 plateau + 1 margin
        assert len(result.all_trials) < 40  # well before budget

    @pytest.mark.asyncio
    async def test_wdk_called_with_merged_params(self) -> None:
        """WDK should receive fixed_parameters + optimised params merged."""
        mock_wdk = AsyncMock(return_value=_make_wdk_result(pos_recall=0.8, neg_fpr=0.1))
        specs = [
            ParameterSpec(
                name="fold_change", param_type="numeric", min_value=1.0, max_value=16.0
            )
        ]
        cfg = OptimizationConfig(budget=1, objective="f1", method="random")

        with patch(WDK_PATCH, mock_wdk):
            await optimize_search_parameters(
                **COMMON_KWARGS,
                parameter_space=specs,
                config=cfg,
            )

        # Check the WDK was called with merged params
        call_kwargs = mock_wdk.call_args.kwargs
        target_params = call_kwargs["target_parameters"]
        assert "organism" in target_params  # from fixed_parameters
        assert "fold_change" in target_params  # from optimised params
