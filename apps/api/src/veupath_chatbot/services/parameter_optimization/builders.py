"""Trial result construction for parameter optimization."""

from dataclasses import dataclass

from veupath_chatbot.platform.types import JSONValue
from veupath_chatbot.services.experiment.types import ControlTestResult
from veupath_chatbot.services.parameter_optimization.config import (
    OptimizationConfig,
    TrialResult,
)
from veupath_chatbot.services.parameter_optimization.scoring import (
    _compute_score,
)


@dataclass(frozen=True, slots=True)
class TrialMetrics:
    """Intermediate metrics extracted from a WDK result."""

    recall: float | None
    fpr: float | None
    estimated_size: int | None
    positive_hits: int | None
    negative_hits: int | None


def _extract_trial_metrics(wdk_result: ControlTestResult) -> TrialMetrics:
    """Extract recall, FPR, result count, and hit counts from a control-test result."""
    pos = wdk_result.positive
    neg = wdk_result.negative

    return TrialMetrics(
        recall=pos.recall if pos else None,
        fpr=neg.false_positive_rate if neg else None,
        estimated_size=wdk_result.target.estimated_size,
        positive_hits=pos.intersection_count if pos else None,
        negative_hits=neg.intersection_count if neg else None,
    )


# ---------------------------------------------------------------------------
# Trial builders
# ---------------------------------------------------------------------------


def _build_failed_trial(
    *,
    trial_number: int,
    params: dict[str, JSONValue],
    n_positives: int,
    n_negatives: int,
) -> TrialResult:
    """Create a TrialResult for a trial that failed (WDK error or exception)."""
    return TrialResult(
        trial_number=trial_number,
        parameters=params,
        score=0.0,
        recall=None,
        false_positive_rate=None,
        estimated_size=None,
        total_positives=n_positives,
        total_negatives=n_negatives,
    )


def _build_successful_trial(
    *,
    trial_number: int,
    params: dict[str, JSONValue],
    wdk_result: ControlTestResult,
    cfg: OptimizationConfig,
    n_positives: int,
    n_negatives: int,
) -> TrialResult:
    """Create a TrialResult from a successful WDK evaluation."""
    metrics = _extract_trial_metrics(wdk_result)
    score = _compute_score(
        metrics.recall,
        metrics.fpr,
        cfg,
        estimated_size=metrics.estimated_size,
        positive_hits=metrics.positive_hits,
        negative_hits=metrics.negative_hits,
    )
    return TrialResult(
        trial_number=trial_number,
        parameters=params,
        score=score,
        recall=metrics.recall,
        false_positive_rate=metrics.fpr,
        estimated_size=metrics.estimated_size,
        positive_hits=metrics.positive_hits,
        negative_hits=metrics.negative_hits,
        total_positives=n_positives,
        total_negatives=n_negatives,
    )
