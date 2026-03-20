"""Tests for the decomposed trial loop helper functions.

Covers _extract_trial_metrics, _build_failed_trial, _build_successful_trial,
_aggregate_results, and _emit_trial_result from trials.py.
"""

import time
from typing import cast
from unittest.mock import AsyncMock

import optuna
import pytest

from veupath_chatbot.platform.types import JSONObject, JSONValue
from veupath_chatbot.services.parameter_optimization.config import (
    OptimizationConfig,
    ParameterSpec,
    TrialResult,
)
from veupath_chatbot.services.parameter_optimization.trials import (
    _aggregate_results,
    _build_failed_trial,
    _build_successful_trial,
    _emit_trial_result,
    _extract_trial_metrics,
    _TrialContext,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ctx(
    *,
    budget: int = 10,
    cfg: OptimizationConfig | None = None,
    progress_callback: AsyncMock | None = None,
    trials: list[TrialResult] | None = None,
    best_trial: TrialResult | None = None,
    parameter_space: list[ParameterSpec] | None = None,
) -> _TrialContext:
    """Build a _TrialContext with sensible defaults for testing."""
    study = optuna.create_study(direction="maximize")
    return _TrialContext(
        site_id="plasmodb",
        record_type="transcript",
        search_name="TestSearch",
        fixed_parameters=cast("JSONObject", {"organism": "P. falciparum"}),
        parameter_space=parameter_space
        or [
            ParameterSpec(
                name="fc", param_type="numeric", min_value=1.0, max_value=16.0
            )
        ],
        controls_search_name="GeneByLocusTag",
        controls_param_name="ds_gene_ids",
        positive_controls=[f"POS_{i}" for i in range(10)],
        negative_controls=[f"NEG_{i}" for i in range(8)],
        controls_value_format="newline",
        controls_extra_parameters=None,
        id_field=None,
        cfg=cfg or OptimizationConfig(objective="f1"),
        optimization_id="opt_test_123",
        budget=budget,
        study=study,
        progress_callback=progress_callback,
        check_cancelled=None,
        start_time=time.monotonic(),
        trials=trials or [],
        best_trial=best_trial,
    )


# ===================================================================
# _extract_trial_metrics
# ===================================================================


class TestExtractTrialMetrics:
    def test_full_wdk_result(self) -> None:
        wdk_result: JSONObject = {
            "target": {"resultCount": 250},
            "positive": {
                "recall": 0.85,
                "intersectionCount": 17,
            },
            "negative": {
                "falsePositiveRate": 0.12,
                "intersectionCount": 3,
            },
        }
        metrics = _extract_trial_metrics(wdk_result)
        assert metrics.recall == 0.85
        assert metrics.fpr == 0.12
        assert metrics.result_count == 250
        assert metrics.positive_hits == 17
        assert metrics.negative_hits == 3

    def test_missing_positive_data(self) -> None:
        wdk_result: JSONObject = {
            "target": {"resultCount": 50},
            "positive": None,
            "negative": None,
        }
        metrics = _extract_trial_metrics(wdk_result)
        assert metrics.recall is None
        assert metrics.fpr is None
        assert metrics.result_count == 50
        assert metrics.positive_hits is None
        assert metrics.negative_hits is None

    def test_missing_target_data(self) -> None:
        wdk_result: JSONObject = {
            "target": None,
            "positive": {"recall": 0.5, "intersectionCount": 5},
            "negative": {"falsePositiveRate": 0.2, "intersectionCount": 2},
        }
        metrics = _extract_trial_metrics(wdk_result)
        assert metrics.recall == 0.5
        assert metrics.fpr == 0.2
        assert metrics.result_count is None

    def test_empty_dicts(self) -> None:
        wdk_result: JSONObject = {
            "target": {},
            "positive": {},
            "negative": {},
        }
        metrics = _extract_trial_metrics(wdk_result)
        assert metrics.recall is None
        assert metrics.fpr is None
        assert metrics.result_count is None
        assert metrics.positive_hits is None
        assert metrics.negative_hits is None


# ===================================================================
# _build_failed_trial
# ===================================================================


class TestBuildFailedTrial:
    def test_basic(self) -> None:
        params: dict[str, JSONValue] = {"fc": 4.0}
        trial = _build_failed_trial(
            trial_number=3,
            params=params,
            n_positives=10,
            n_negatives=8,
        )
        assert trial.trial_number == 3
        assert trial.parameters == {"fc": 4.0}
        assert trial.score == 0.0
        assert trial.recall is None
        assert trial.false_positive_rate is None
        assert trial.result_count is None
        assert trial.total_positives == 10
        assert trial.total_negatives == 8

    def test_zero_controls(self) -> None:
        trial = _build_failed_trial(
            trial_number=1,
            params={},
            n_positives=0,
            n_negatives=0,
        )
        assert trial.total_positives == 0
        assert trial.total_negatives == 0
        assert trial.score == 0.0


# ===================================================================
# _build_successful_trial
# ===================================================================


class TestBuildSuccessfulTrial:
    def test_basic_f1_scoring(self) -> None:
        wdk_result: JSONObject = {
            "target": {"resultCount": 100},
            "positive": {
                "recall": 0.8,
                "intersectionCount": 8,
            },
            "negative": {
                "falsePositiveRate": 0.1,
                "intersectionCount": 1,
            },
        }
        cfg = OptimizationConfig(objective="f1")
        params: dict[str, JSONValue] = {"fc": 2.0}
        trial = _build_successful_trial(
            trial_number=5,
            params=params,
            wdk_result=wdk_result,
            cfg=cfg,
            n_positives=10,
            n_negatives=8,
        )
        assert trial.trial_number == 5
        assert trial.parameters == {"fc": 2.0}
        assert trial.score > 0
        assert trial.recall == 0.8
        assert trial.false_positive_rate == 0.1
        assert trial.result_count == 100
        assert trial.positive_hits == 8
        assert trial.negative_hits == 1
        assert trial.total_positives == 10
        assert trial.total_negatives == 8

    def test_no_positive_negative_data(self) -> None:
        """When positive/negative data is None, score should still compute."""
        wdk_result: JSONObject = {
            "target": {"resultCount": 50},
            "positive": None,
            "negative": None,
        }
        cfg = OptimizationConfig(objective="f1")
        trial = _build_successful_trial(
            trial_number=1,
            params={"fc": 1.0},
            wdk_result=wdk_result,
            cfg=cfg,
            n_positives=10,
            n_negatives=8,
        )
        assert trial.recall is None
        assert trial.false_positive_rate is None
        # With None recall/fpr, score should be 0.0 for f1
        assert trial.score == 0.0

    def test_recall_objective(self) -> None:
        wdk_result: JSONObject = {
            "target": {"resultCount": 200},
            "positive": {"recall": 0.7, "intersectionCount": 7},
            "negative": {"falsePositiveRate": 0.5, "intersectionCount": 4},
        }
        cfg = OptimizationConfig(objective="recall")
        trial = _build_successful_trial(
            trial_number=2,
            params={"fc": 3.0},
            wdk_result=wdk_result,
            cfg=cfg,
            n_positives=10,
            n_negatives=8,
        )
        assert trial.score == 0.7


# ===================================================================
# _aggregate_results
# ===================================================================


class TestAggregateResults:
    def test_completed_no_trials(self) -> None:
        ctx = _make_ctx()
        result = _aggregate_results(ctx, status="completed")
        assert result.optimization_id == "opt_test_123"
        assert result.status == "completed"
        assert result.best_trial is None
        assert result.all_trials == []
        assert result.pareto_frontier == []
        assert result.total_time_seconds >= 0
        assert result.error_message is None

    def test_completed_with_trials(self) -> None:
        t = TrialResult(
            trial_number=1,
            parameters={"fc": 2.0},
            score=0.85,
            recall=0.9,
            false_positive_rate=0.1,
            result_count=100,
            total_positives=10,
            total_negatives=8,
        )
        ctx = _make_ctx(trials=[t], best_trial=t)
        result = _aggregate_results(ctx, status="completed")
        assert result.best_trial is t
        assert len(result.all_trials) == 1
        assert len(result.pareto_frontier) == 1
        assert result.status == "completed"

    def test_error_status_with_message(self) -> None:
        ctx = _make_ctx()
        result = _aggregate_results(
            ctx, status="error", error_message="All trials failed"
        )
        assert result.status == "error"
        assert result.error_message == "All trials failed"

    def test_cancelled_status(self) -> None:
        ctx = _make_ctx()
        result = _aggregate_results(ctx, status="cancelled")
        assert result.status == "cancelled"

    def test_sensitivity_populated(self) -> None:
        """Sensitivity dict should have entries for each param spec."""
        specs = [
            ParameterSpec(name="x", param_type="numeric", min_value=0, max_value=1),
            ParameterSpec(name="y", param_type="numeric", min_value=0, max_value=1),
        ]
        ctx = _make_ctx(parameter_space=specs)
        result = _aggregate_results(ctx, status="completed")
        assert "x" in result.sensitivity
        assert "y" in result.sensitivity


# ===================================================================
# _emit_trial_result
# ===================================================================


class TestEmitTrialResult:
    @pytest.mark.asyncio
    async def test_emits_for_successful_trial(self) -> None:
        callback = AsyncMock()
        ctx = _make_ctx(progress_callback=callback, budget=10)
        trial = TrialResult(
            trial_number=3,
            parameters={"fc": 2.0},
            score=0.85,
            recall=0.9,
            false_positive_rate=0.1,
            result_count=100,
        )
        await _emit_trial_result(ctx, trial_num=3, trial_result=trial)
        callback.assert_called_once()
        event = callback.call_args[0][0]
        data = event["data"]
        assert data["status"] == "running"
        assert data["currentTrial"] == 3
        assert data["totalTrials"] == 10

    @pytest.mark.asyncio
    async def test_emits_for_failed_trial_with_error(self) -> None:
        callback = AsyncMock()
        ctx = _make_ctx(progress_callback=callback)
        trial = TrialResult(
            trial_number=1,
            parameters={"fc": 1.0},
            score=0.0,
            recall=None,
            false_positive_rate=None,
            result_count=None,
        )
        await _emit_trial_result(
            ctx, trial_num=1, trial_result=trial, wdk_error="WDK 422"
        )
        callback.assert_called_once()
        event = callback.call_args[0][0]
        data = event["data"]
        trial_data = data["trial"]
        assert isinstance(trial_data, dict)
        assert trial_data.get("error") == "WDK 422"

    @pytest.mark.asyncio
    async def test_no_callback_no_error(self) -> None:
        """When no progress_callback is set, _emit_trial_result should be a no-op."""
        ctx = _make_ctx(progress_callback=None)
        trial = TrialResult(
            trial_number=1,
            parameters={},
            score=0.5,
            recall=0.8,
            false_positive_rate=0.1,
            result_count=100,
        )
        # Should not raise
        await _emit_trial_result(ctx, trial_num=1, trial_result=trial)

    @pytest.mark.asyncio
    async def test_includes_best_trial(self) -> None:
        callback = AsyncMock()
        best = TrialResult(
            trial_number=1,
            parameters={"fc": 2.0},
            score=0.9,
            recall=0.95,
            false_positive_rate=0.05,
            result_count=50,
        )
        ctx = _make_ctx(progress_callback=callback, best_trial=best)
        current = TrialResult(
            trial_number=2,
            parameters={"fc": 3.0},
            score=0.7,
            recall=0.8,
            false_positive_rate=0.2,
            result_count=100,
        )
        ctx.trials.append(best)
        ctx.trials.append(current)
        await _emit_trial_result(ctx, trial_num=2, trial_result=current)
        callback.assert_called_once()
        event = callback.call_args[0][0]
        data = event["data"]
        best_data = data["bestTrial"]
        assert isinstance(best_data, dict)
        assert best_data["trialNumber"] == 1
