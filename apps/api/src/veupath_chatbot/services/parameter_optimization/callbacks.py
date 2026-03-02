"""SSE progress callbacks for parameter optimization."""

from __future__ import annotations

from typing import cast

from veupath_chatbot.platform.types import JSONArray, JSONObject, JSONValue
from veupath_chatbot.services.parameter_optimization.config import (
    ProgressCallback,
    TrialResult,
)
from veupath_chatbot.services.parameter_optimization.scoring import (
    _trial_to_json,
)


async def emit_started(
    callback: ProgressCallback,
    *,
    optimization_id: str,
    search_name: str,
    record_type: str,
    budget: int,
    objective: str,
    positive_controls_count: int,
    negative_controls_count: int,
    param_space_json: JSONArray,
) -> None:
    await callback(
        {
            "type": "optimization_progress",
            "data": {
                "optimizationId": optimization_id,
                "status": "started",
                "searchName": search_name,
                "recordType": record_type,
                "budget": budget,
                "objective": objective,
                "positiveControlsCount": positive_controls_count,
                "negativeControlsCount": negative_controls_count,
                "parameterSpace": param_space_json,
                "currentTrial": 0,
                "totalTrials": budget,
                "bestTrial": None,
                "recentTrials": [],
            },
        }
    )


async def emit_trial_progress(
    callback: ProgressCallback,
    *,
    optimization_id: str,
    trial_num: int,
    budget: int,
    trial_json: JSONObject,
    best_trial: TrialResult | None,
    recent_trials: list[TrialResult],
) -> None:
    await callback(
        {
            "type": "optimization_progress",
            "data": {
                "optimizationId": optimization_id,
                "status": "running",
                "currentTrial": trial_num,
                "totalTrials": budget,
                "trial": trial_json,
                "bestTrial": (_trial_to_json(best_trial) if best_trial else None),
                "recentTrials": [_trial_to_json(t) for t in recent_trials],
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
    *,
    optimization_id: str,
    status: str,
    budget: int,
    trials: list[TrialResult],
    best_trial: TrialResult | None,
    pareto: list[TrialResult],
    sensitivity: dict[str, float],
    elapsed: float,
) -> None:
    await callback(
        {
            "type": "optimization_progress",
            "data": {
                "optimizationId": optimization_id,
                "status": status,
                "currentTrial": len(trials),
                "totalTrials": budget,
                "bestTrial": _trial_to_json(best_trial) if best_trial else None,
                "allTrials": [_trial_to_json(t) for t in trials],
                "paretoFrontier": [_trial_to_json(t) for t in pareto],
                "sensitivity": cast(JSONValue, sensitivity),
                "totalTimeSeconds": round(elapsed, 2),
            },
        }
    )
