"""Tests for decomposed trial-loop helpers in parameter_optimization.trials.

Tests each extracted helper function independently before they are wired
into run_trial_loop().
"""

import dataclasses
import time
from enum import Enum
from typing import Any, cast
from unittest.mock import AsyncMock, patch

import optuna
import pytest

from veupath_chatbot.platform.types import JSONObject, JSONValue
from veupath_chatbot.services.experiment.types.control_result import (
    ControlSetData,
    ControlTargetData,
    ControlTestResult,
)
from veupath_chatbot.services.parameter_optimization.config import (
    OptimizationConfig,
    ParameterSpec,
    TrialResult,
)
from veupath_chatbot.services.parameter_optimization.trials import (
    EarlyStopReason,
    TrialMetrics,
    _aggregate_results,
    _build_failed_trial,
    _build_successful_trial,
    _check_early_stop,
    _extract_trial_metrics,
    _should_early_stop,
    _TrialContext,
    _unpack_gather_result,
    run_trial_loop,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _wdk_result(
    *,
    estimated_size: int = 100,
    recall: float = 0.8,
    fpr: float = 0.1,
    pos_intersection: int = 8,
    neg_intersection: int = 1,
) -> ControlTestResult:
    """Build a realistic WDK result."""
    return ControlTestResult(
        target=ControlTargetData(estimated_size=estimated_size),
        positive=ControlSetData(recall=recall, intersection_count=pos_intersection),
        negative=ControlSetData(
            false_positive_rate=fpr,
            intersection_count=neg_intersection,
        ),
    )


def _make_ctx(
    *,
    budget: int = 10,
    method: str = "random",
    objective: str = "f1",
    trials: list[TrialResult] | None = None,
    best_trial: TrialResult | None = None,
) -> _TrialContext:
    """Create a minimal _TrialContext for testing."""
    cfg = OptimizationConfig(budget=budget, objective=objective, method=method)
    study = optuna.create_study(direction="maximize")
    return _TrialContext(
        site_id="plasmodb",
        record_type="transcript",
        search_name="TestSearch",
        fixed_parameters=cast("JSONObject", {"organism": "P. falciparum"}),
        parameter_space=[
            ParameterSpec(
                name="fold_change",
                param_type="numeric",
                min_value=1.0,
                max_value=16.0,
            )
        ],
        controls_search_name="GeneByLocusTag",
        controls_param_name="ds_gene_ids",
        positive_controls=[f"POS_{i}" for i in range(10)],
        negative_controls=[f"NEG_{i}" for i in range(8)],
        controls_value_format="newline",
        controls_extra_parameters=None,
        id_field=None,
        cfg=cfg,
        optimization_id="test_opt",
        budget=budget,
        study=study,
        progress_callback=None,
        check_cancelled=None,
        start_time=time.monotonic(),
        trials=trials if trials is not None else [],
        best_trial=best_trial,
    )


# ===================================================================
# _extract_trial_metrics
# ===================================================================


class TestExtractTrialMetrics:
    def test_full_result(self) -> None:
        wdk = _wdk_result(
            estimated_size=150,
            recall=0.9,
            fpr=0.05,
            pos_intersection=9,
            neg_intersection=2,
        )
        m = _extract_trial_metrics(wdk)
        assert m.recall == 0.9
        assert m.fpr == 0.05
        assert m.estimated_size == 150
        assert m.positive_hits == 9
        assert m.negative_hits == 2

    def test_missing_positive(self) -> None:
        wdk = ControlTestResult(
            target=ControlTargetData(estimated_size=50),
            negative=ControlSetData(false_positive_rate=0.1, intersection_count=1),
        )
        m = _extract_trial_metrics(wdk)
        assert m.recall is None
        assert m.positive_hits is None
        assert m.fpr == 0.1
        assert m.estimated_size == 50

    def test_missing_negative(self) -> None:
        wdk = ControlTestResult(
            target=ControlTargetData(estimated_size=50),
            positive=ControlSetData(recall=0.8, intersection_count=8),
        )
        m = _extract_trial_metrics(wdk)
        assert m.fpr is None
        assert m.negative_hits is None
        assert m.recall == 0.8

    def test_missing_target(self) -> None:
        wdk = ControlTestResult(
            positive=ControlSetData(recall=0.8, intersection_count=8),
            negative=ControlSetData(false_positive_rate=0.1, intersection_count=1),
        )
        m = _extract_trial_metrics(wdk)
        assert m.estimated_size is None

    def test_empty_result(self) -> None:
        m = _extract_trial_metrics(ControlTestResult())
        assert m.recall is None
        assert m.fpr is None
        assert m.estimated_size is None
        assert m.positive_hits is None
        assert m.negative_hits is None

    def test_none_sections_produce_none(self) -> None:
        wdk = ControlTestResult(positive=None, negative=None)
        m = _extract_trial_metrics(wdk)
        assert m.recall is None
        assert m.fpr is None
        assert m.estimated_size is None


# ===================================================================
# TrialMetrics dataclass
# ===================================================================


class TestTrialMetrics:
    def test_frozen(self) -> None:
        assert dataclasses.fields(TrialMetrics)  # is a dataclass
        m = TrialMetrics(
            recall=0.8, fpr=0.1, estimated_size=100, positive_hits=8, negative_hits=1
        )
        assert m.recall == 0.8
        # Frozen dataclasses should not allow __dict__ (slots=True)
        assert not hasattr(m, "__dict__")


# ===================================================================
# _build_failed_trial
# ===================================================================


class TestBuildFailedTrial:
    def test_basic(self) -> None:
        params: dict[str, JSONValue] = {"fold_change": 4.0}
        t = _build_failed_trial(
            trial_number=3, params=params, n_positives=10, n_negatives=8
        )
        assert t.trial_number == 3
        assert t.parameters == params
        assert t.score == 0.0
        assert t.recall is None
        assert t.false_positive_rate is None
        assert t.estimated_size is None
        assert t.positive_hits is None
        assert t.negative_hits is None
        assert t.total_positives == 10
        assert t.total_negatives == 8

    def test_zero_controls(self) -> None:
        t = _build_failed_trial(trial_number=1, params={}, n_positives=0, n_negatives=0)
        assert t.total_positives == 0
        assert t.total_negatives == 0


# ===================================================================
# _build_successful_trial
# ===================================================================


class TestBuildSuccessfulTrial:
    def test_basic(self) -> None:
        wdk = _wdk_result(
            estimated_size=150,
            recall=0.9,
            fpr=0.05,
            pos_intersection=9,
            neg_intersection=2,
        )
        cfg = OptimizationConfig(objective="f1")
        t = _build_successful_trial(
            trial_number=5,
            params={"fold_change": 4.0},
            wdk_result=wdk,
            cfg=cfg,
            n_positives=10,
            n_negatives=8,
        )
        assert t.trial_number == 5
        assert t.score > 0
        assert t.recall == 0.9
        assert t.false_positive_rate == 0.05
        assert t.estimated_size == 150
        assert t.positive_hits == 9
        assert t.negative_hits == 2
        assert t.total_positives == 10
        assert t.total_negatives == 8

    def test_empty_wdk_result(self) -> None:
        cfg = OptimizationConfig(objective="f1")
        t = _build_successful_trial(
            trial_number=1,
            params={},
            wdk_result=ControlTestResult(),
            cfg=cfg,
            n_positives=0,
            n_negatives=0,
        )
        assert t.score == 0.0
        assert t.recall is None
        assert t.false_positive_rate is None

    def test_none_sections(self) -> None:
        wdk = ControlTestResult(positive=None, negative=None)
        cfg = OptimizationConfig(objective="f1")
        t = _build_successful_trial(
            trial_number=1,
            params={},
            wdk_result=wdk,
            cfg=cfg,
            n_positives=0,
            n_negatives=0,
        )
        assert t.recall is None
        assert t.false_positive_rate is None
        assert t.estimated_size is None


# ===================================================================
# _unpack_gather_result
# ===================================================================


class TestUnpackGatherResult:
    def test_success_pair(self) -> None:
        ctr = ControlTestResult()
        raw: tuple[ControlTestResult | None, str] = (ctr, "")
        wdk_result, wdk_error = _unpack_gather_result(raw, 1, {})
        assert wdk_result is ctr
        assert wdk_error == ""

    def test_error_pair(self) -> None:
        raw: tuple[ControlTestResult | None, str] = (None, "WDK 422")
        wdk_result, wdk_error = _unpack_gather_result(raw, 1, {})
        assert wdk_result is None
        assert wdk_error == "WDK 422"

    def test_base_exception(self) -> None:
        raw = RuntimeError("boom")
        wdk_result, wdk_error = _unpack_gather_result(raw, 1, {})
        assert wdk_result is None
        assert "boom" in wdk_error


# ===================================================================
# EarlyStopReason / _check_early_stop (pure, no logging)
# ===================================================================


class TestCheckEarlyStopPure:
    """Tests for the pure _check_early_stop function (no ctx, no logging)."""

    def test_perfect_score(self) -> None:
        best = TrialResult(
            trial_number=1,
            parameters={},
            score=1.0,
            recall=1.0,
            false_positive_rate=0.0,
            estimated_size=50,
        )
        assert (
            _check_early_stop(best_trial=best, trials_since_improvement=0)
            == EarlyStopReason.PERFECT_SCORE
        )

    def test_plateau(self) -> None:
        best = TrialResult(
            trial_number=1,
            parameters={},
            score=0.5,
            recall=0.5,
            false_positive_rate=0.3,
            estimated_size=100,
        )
        assert (
            _check_early_stop(best_trial=best, trials_since_improvement=10)
            == EarlyStopReason.PLATEAU
        )

    def test_no_stop(self) -> None:
        best = TrialResult(
            trial_number=1,
            parameters={},
            score=0.5,
            recall=0.5,
            false_positive_rate=0.3,
            estimated_size=100,
        )
        assert _check_early_stop(best_trial=best, trials_since_improvement=3) is None

    def test_no_best_trial(self) -> None:
        assert _check_early_stop(best_trial=None, trials_since_improvement=0) is None

    def test_custom_thresholds(self) -> None:
        best = TrialResult(
            trial_number=1,
            parameters={},
            score=0.8,
            recall=0.8,
            false_positive_rate=0.1,
            estimated_size=50,
        )
        assert (
            _check_early_stop(
                best_trial=best,
                trials_since_improvement=0,
                perfect_score_threshold=0.7,
            )
            == EarlyStopReason.PERFECT_SCORE
        )
        assert (
            _check_early_stop(
                best_trial=best,
                trials_since_improvement=3,
                plateau_window=3,
            )
            == EarlyStopReason.PLATEAU
        )

    def test_enum_values(self) -> None:
        assert EarlyStopReason.PERFECT_SCORE.value == "perfect_score"
        assert EarlyStopReason.PLATEAU.value == "plateau"
        assert issubclass(EarlyStopReason, Enum)


# ===================================================================
# _should_early_stop (ctx wrapper with logging)
# ===================================================================


class TestShouldEarlyStop:
    def test_perfect_score(self) -> None:
        best = TrialResult(
            trial_number=1,
            parameters={},
            score=1.0,
            recall=1.0,
            false_positive_rate=0.0,
            estimated_size=50,
        )
        ctx = _make_ctx()
        ctx.best_trial = best
        assert _should_early_stop(ctx, trials_since_improvement=0, trial_num=1) is True

    def test_plateau(self) -> None:
        best = TrialResult(
            trial_number=1,
            parameters={},
            score=0.5,
            recall=0.5,
            false_positive_rate=0.3,
            estimated_size=100,
        )
        ctx = _make_ctx()
        ctx.best_trial = best
        assert _should_early_stop(ctx, trials_since_improvement=10, trial_num=1) is True

    def test_no_stop(self) -> None:
        best = TrialResult(
            trial_number=1,
            parameters={},
            score=0.5,
            recall=0.5,
            false_positive_rate=0.3,
            estimated_size=100,
        )
        ctx = _make_ctx()
        ctx.best_trial = best
        assert _should_early_stop(ctx, trials_since_improvement=3, trial_num=1) is False

    def test_no_best_trial_no_stop(self) -> None:
        ctx = _make_ctx()
        assert _should_early_stop(ctx, trials_since_improvement=0, trial_num=1) is False

    def test_score_just_below_threshold(self) -> None:
        best = TrialResult(
            trial_number=1,
            parameters={},
            score=0.999,
            recall=0.999,
            false_positive_rate=0.001,
            estimated_size=50,
        )
        ctx = _make_ctx()
        ctx.best_trial = best
        assert _should_early_stop(ctx, trials_since_improvement=0, trial_num=1) is False

    def test_plateau_exact_boundary(self) -> None:
        best = TrialResult(
            trial_number=1,
            parameters={},
            score=0.5,
            recall=0.5,
            false_positive_rate=0.3,
            estimated_size=100,
        )
        ctx = _make_ctx()
        ctx.best_trial = best
        assert _should_early_stop(ctx, trials_since_improvement=9, trial_num=1) is False
        assert _should_early_stop(ctx, trials_since_improvement=10, trial_num=1) is True


# ===================================================================
# _aggregate_results
# ===================================================================


class TestAggregateResults:
    def test_completed_no_trials(self) -> None:
        ctx = _make_ctx()
        result = _aggregate_results(ctx, status="completed")
        assert result.optimization_id == "test_opt"
        assert result.status == "completed"
        assert result.best_trial is None
        assert result.all_trials == []
        assert result.pareto_frontier == []
        assert result.error_message is None
        assert result.total_time_seconds >= 0

    def test_error_with_message(self) -> None:
        ctx = _make_ctx()
        result = _aggregate_results(
            ctx, status="error", error_message="something broke"
        )
        assert result.status == "error"
        assert result.error_message == "something broke"

    def test_with_trials(self) -> None:
        t1 = TrialResult(
            trial_number=1,
            parameters={},
            score=0.8,
            recall=0.9,
            false_positive_rate=0.1,
            estimated_size=100,
        )
        t2 = TrialResult(
            trial_number=2,
            parameters={},
            score=0.5,
            recall=0.6,
            false_positive_rate=0.3,
            estimated_size=200,
        )
        ctx = _make_ctx(trials=[t1, t2], best_trial=t1)
        result = _aggregate_results(ctx, status="completed")
        assert result.best_trial is t1
        assert len(result.all_trials) == 2
        assert len(result.pareto_frontier) >= 1

    def test_cancelled_status(self) -> None:
        ctx = _make_ctx()
        result = _aggregate_results(ctx, status="cancelled")
        assert result.status == "cancelled"


# ===================================================================
# run_trial_loop integration (ensure decomposition didn't break it)
# ===================================================================


WDK_PATCH = (
    "veupath_chatbot.services.parameter_optimization.trials"
    ".run_positive_negative_controls"
)


def _make_wdk_result(
    *,
    estimated_size: int = 100,
    pos_recall: float = 0.8,
    neg_fpr: float = 0.1,
) -> ControlTestResult:
    pos = [f"POS_{i}" for i in range(10)]
    neg = [f"NEG_{i}" for i in range(8)]
    n_pos_found = int(len(pos) * pos_recall)
    n_neg_found = int(len(neg) * neg_fpr)
    return ControlTestResult(
        target=ControlTargetData(estimated_size=estimated_size),
        positive=ControlSetData(
            recall=n_pos_found / len(pos) if n_pos_found > 0 else None,
            intersection_count=n_pos_found,
        ),
        negative=ControlSetData(
            false_positive_rate=n_neg_found / len(neg) if n_neg_found > 0 else None,
            intersection_count=n_neg_found,
        ),
    )


class TestRunTrialLoopIntegration:
    """Ensure the decomposed run_trial_loop still works end-to-end."""

    @pytest.mark.asyncio
    async def test_successful_run(self) -> None:
        mock_wdk = AsyncMock(return_value=_make_wdk_result(pos_recall=0.8, neg_fpr=0.1))
        ctx = _make_ctx(budget=5)
        with patch(WDK_PATCH, mock_wdk):
            result = await run_trial_loop(ctx)
        assert result.status == "completed"
        assert result.best_trial is not None
        assert result.best_trial.score > 0
        assert len(result.all_trials) == 5

    @pytest.mark.asyncio
    async def test_all_fail_early_abort(self) -> None:
        mock_wdk = AsyncMock(side_effect=RuntimeError("fail"))
        ctx = _make_ctx(budget=40)
        with patch(WDK_PATCH, mock_wdk):
            result = await run_trial_loop(ctx)
        assert result.status == "error"
        assert result.best_trial is None
        assert len(result.all_trials) < 40

    @pytest.mark.asyncio
    async def test_cancellation(self) -> None:
        call_count = 0

        async def _counting_wdk(_config: Any, **kwargs: Any) -> ControlTestResult:
            nonlocal call_count
            call_count += 1
            return _make_wdk_result(pos_recall=0.8, neg_fpr=0.1)

        ctx = _make_ctx(budget=40)
        ctx.check_cancelled = lambda: call_count >= 3
        with patch(WDK_PATCH, _counting_wdk):
            result = await run_trial_loop(ctx)
        assert result.status == "cancelled"
        assert len(result.all_trials) < 40

    @pytest.mark.asyncio
    async def test_early_stop_perfect_score(self) -> None:
        mock_wdk = AsyncMock(return_value=_make_wdk_result(pos_recall=1.0, neg_fpr=0.0))
        ctx = _make_ctx(budget=40)
        with patch(WDK_PATCH, mock_wdk):
            result = await run_trial_loop(ctx)
        assert result.status == "completed"
        assert len(result.all_trials) <= 4  # first batch at most
        assert result.best_trial is not None
        assert result.best_trial.score >= 0.99

    @pytest.mark.asyncio
    async def test_progress_callback_fires(self) -> None:
        mock_wdk = AsyncMock(return_value=_make_wdk_result(pos_recall=0.8, neg_fpr=0.1))
        events: list[JSONObject] = []

        async def capture(event: JSONObject) -> None:
            events.append(event)

        ctx = _make_ctx(budget=3)
        ctx.progress_callback = capture
        with patch(WDK_PATCH, mock_wdk):
            await run_trial_loop(ctx)
        # One event per trial (start/complete events are in core.py)
        assert len(events) == 3

    @pytest.mark.asyncio
    async def test_exception_in_loop_returns_error_result(self) -> None:
        """An unexpected exception in the loop returns an error result."""
        ctx = _make_ctx(budget=3)

        def broken_ask() -> optuna.trial.Trial:
            msg = "study broken"
            raise RuntimeError(msg)

        with patch.object(ctx.study, "ask", broken_ask):
            result = await run_trial_loop(ctx)
        assert result.status == "error"
        assert "study broken" in (result.error_message or "")

    @pytest.mark.asyncio
    async def test_failed_trials_emit_progress_with_error(self) -> None:
        mock_wdk = AsyncMock(side_effect=RuntimeError("wdk fail"))
        events: list[JSONObject] = []

        async def capture(event: JSONObject) -> None:
            events.append(event)

        ctx = _make_ctx(budget=3)
        ctx.progress_callback = capture
        with patch(WDK_PATCH, mock_wdk):
            await run_trial_loop(ctx)
        # All 3 trials should have progress events
        assert len(events) >= 3
