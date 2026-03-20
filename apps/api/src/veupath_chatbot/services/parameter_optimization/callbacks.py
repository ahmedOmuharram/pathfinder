"""SSE progress callbacks for parameter optimization."""

from dataclasses import dataclass
from typing import cast

from veupath_chatbot.platform.types import JSONArray, JSONObject, JSONValue
from veupath_chatbot.services.parameter_optimization.config import (
    ProgressCallback,
    TrialResult,
)
from veupath_chatbot.services.parameter_optimization.scoring import (
    _trial_to_json,
)


@dataclass(frozen=True, slots=True)
class OptimizationStartedEvent:
    """Data for an optimization_started SSE event."""

    optimization_id: str
    search_name: str
    record_type: str
    budget: int
    objective: str
    positive_controls_count: int
    negative_controls_count: int
    param_space_json: JSONArray


@dataclass(frozen=True, slots=True)
class TrialProgressEvent:
    """Data for a trial_progress SSE event."""

    optimization_id: str
    trial_num: int
    budget: int
    trial_json: JSONObject
    best_trial: TrialResult | None
    recent_trials: list[TrialResult]


@dataclass(frozen=True, slots=True)
class OptimizationCompletedEvent:
    """Data for an optimization_completed SSE event."""

    optimization_id: str
    status: str
    budget: int
    trials: list[TrialResult]
    best_trial: TrialResult | None
    pareto: list[TrialResult]
    sensitivity: dict[str, float]
    elapsed: float


async def emit_started(
    callback: ProgressCallback,
    event: OptimizationStartedEvent,
) -> None:
    await callback(
        {
            "type": "optimization_progress",
            "data": {
                "optimizationId": event.optimization_id,
                "status": "started",
                "searchName": event.search_name,
                "recordType": event.record_type,
                "budget": event.budget,
                "objective": event.objective,
                "positiveControlsCount": event.positive_controls_count,
                "negativeControlsCount": event.negative_controls_count,
                "parameterSpace": event.param_space_json,
                "currentTrial": 0,
                "totalTrials": event.budget,
                "bestTrial": None,
                "recentTrials": [],
            },
        }
    )


async def emit_trial_progress(
    callback: ProgressCallback,
    event: TrialProgressEvent,
) -> None:
    await callback(
        {
            "type": "optimization_progress",
            "data": {
                "optimizationId": event.optimization_id,
                "status": "running",
                "currentTrial": event.trial_num,
                "totalTrials": event.budget,
                "trial": event.trial_json,
                "bestTrial": (
                    _trial_to_json(event.best_trial) if event.best_trial else None
                ),
                "recentTrials": [_trial_to_json(t) for t in event.recent_trials],
            },
        }
    )


async def emit_error(
    callback: ProgressCallback,
    *,
    optimization_id: str,
    error: str,
) -> None:
    await callback(
        {
            "type": "optimization_progress",
            "data": {
                "optimizationId": optimization_id,
                "status": "error",
                "error": error,
            },
        }
    )


async def emit_completed(
    callback: ProgressCallback,
    event: OptimizationCompletedEvent,
) -> None:
    await callback(
        {
            "type": "optimization_progress",
            "data": {
                "optimizationId": event.optimization_id,
                "status": event.status,
                "currentTrial": len(event.trials),
                "totalTrials": event.budget,
                "bestTrial": _trial_to_json(event.best_trial)
                if event.best_trial
                else None,
                "allTrials": [_trial_to_json(t) for t in event.trials],
                "paretoFrontier": [_trial_to_json(t) for t in event.pareto],
                "sensitivity": cast("JSONValue", event.sensitivity),
                "totalTimeSeconds": round(event.elapsed, 2),
            },
        }
    )
