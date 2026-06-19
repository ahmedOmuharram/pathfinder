from __future__ import annotations

from pathfinder.services.parameter_optimization.config import TrialResult
from pathfinder.services.parameter_optimization.early_stop import (
    EarlyStopReason,
    _check_early_stop,
    _should_abort_on_failures,
    _should_early_stop,
)


def _trial(score: float) -> TrialResult:
    return TrialResult(
        trial_number=0,
        parameters={},
        score=score,
        recall=None,
        false_positive_rate=None,
        estimated_size=None,
    )


class TestCheckEarlyStop:
    def test_perfect_score_at_threshold_stops(self) -> None:
        assert (
            _check_early_stop(best_trial=_trial(0.9999), trials_since_improvement=0)
            == EarlyStopReason.PERFECT_SCORE
        )

    def test_just_below_perfect_does_not_stop(self) -> None:
        assert (
            _check_early_stop(best_trial=_trial(0.9998), trials_since_improvement=3)
            is None
        )

    def test_plateau_at_window_stops(self) -> None:
        assert (
            _check_early_stop(best_trial=_trial(0.5), trials_since_improvement=10)
            == EarlyStopReason.PLATEAU
        )

    def test_one_short_of_window_does_not_stop(self) -> None:
        assert (
            _check_early_stop(best_trial=_trial(0.5), trials_since_improvement=9)
            is None
        )

    def test_perfect_score_takes_precedence_over_plateau(self) -> None:
        assert (
            _check_early_stop(best_trial=_trial(1.0), trials_since_improvement=10)
            == EarlyStopReason.PERFECT_SCORE
        )

    def test_plateau_fires_even_without_a_best_trial(self) -> None:
        assert (
            _check_early_stop(best_trial=None, trials_since_improvement=10)
            == EarlyStopReason.PLATEAU
        )


class TestShouldEarlyStop:
    def test_returns_true_on_perfect_score(self) -> None:
        assert (
            _should_early_stop(
                optimization_id="opt-1",
                best_trial=_trial(0.9999),
                trials_since_improvement=0,
                trial_num=4,
            )
            is True
        )

    def test_returns_false_while_improving(self) -> None:
        assert (
            _should_early_stop(
                optimization_id="opt-1",
                best_trial=_trial(0.5),
                trials_since_improvement=2,
                trial_num=4,
            )
            is False
        )


class TestShouldAbortOnFailures:
    def test_aborts_after_five_failures_with_no_best(self) -> None:
        msg = _should_abort_on_failures(
            optimization_id="opt-1",
            best_trial=None,
            consecutive_failures=5,
            wdk_error="500 from WDK",
        )
        assert msg == "Aborted after 5 consecutive failures. Last error: 500 from WDK"

    def test_does_not_abort_when_a_best_trial_exists(self) -> None:
        assert (
            _should_abort_on_failures(
                optimization_id="opt-1",
                best_trial=_trial(0.7),
                consecutive_failures=9,
                wdk_error="500 from WDK",
            )
            is None
        )

    def test_does_not_abort_below_threshold(self) -> None:
        assert (
            _should_abort_on_failures(
                optimization_id="opt-1",
                best_trial=None,
                consecutive_failures=4,
                wdk_error="timeout",
            )
            is None
        )
