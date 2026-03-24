"""Early-stop logic for the parameter optimization trial loop."""

from enum import StrEnum

from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.services.parameter_optimization.config import TrialResult

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_CONSECUTIVE_FAILURES = 5
_PLATEAU_WINDOW = 10
_PERFECT_SCORE_THRESHOLD = 0.9999


class EarlyStopReason(StrEnum):
    """Why the optimisation loop stopped early."""

    PERFECT_SCORE = "perfect_score"
    PLATEAU = "plateau"


def _check_early_stop(
    *,
    best_trial: TrialResult | None,
    trials_since_improvement: int,
    plateau_window: int = _PLATEAU_WINDOW,
    perfect_score_threshold: float = _PERFECT_SCORE_THRESHOLD,
) -> EarlyStopReason | None:
    """Pure early-stop check (no side effects, no logging).

    Returns the reason for stopping, or None to continue.
    """
    if best_trial and best_trial.score >= perfect_score_threshold:
        return EarlyStopReason.PERFECT_SCORE
    if trials_since_improvement >= plateau_window:
        return EarlyStopReason.PLATEAU
    return None


def _should_early_stop(
    *,
    optimization_id: str,
    best_trial: TrialResult | None,
    trials_since_improvement: int,
    trial_num: int,
) -> bool:
    """Check whether the loop should stop early (with logging)."""
    reason = _check_early_stop(
        best_trial=best_trial,
        trials_since_improvement=trials_since_improvement,
    )
    if reason is None:
        return False

    match reason:
        case EarlyStopReason.PERFECT_SCORE:
            logger.info(
                "Early stop: perfect score reached",
                optimization_id=optimization_id,
                score=best_trial.score if best_trial else 0,
                trial=trial_num,
            )
        case EarlyStopReason.PLATEAU:
            logger.info(
                "Early stop: score plateau detected",
                optimization_id=optimization_id,
                best_score=best_trial.score if best_trial else 0,
                trials_without_improvement=trials_since_improvement,
                trial=trial_num,
            )
    return True


def _should_abort_on_failures(
    *,
    optimization_id: str,
    best_trial: TrialResult | None,
    consecutive_failures: int,
    wdk_error: str,
) -> str | None:
    """Return an error message if the loop should abort due to failures.

    Returns None if the loop should continue.
    """
    if consecutive_failures >= _MAX_CONSECUTIVE_FAILURES and best_trial is None:
        msg = (
            f"Aborted after {consecutive_failures} consecutive failures. "
            f"Last error: {wdk_error}"
        )
        logger.error(
            "Aborting optimisation: all trials failed",
            optimization_id=optimization_id,
            consecutive_failures=consecutive_failures,
            last_error=wdk_error,
        )
        return msg
    return None
