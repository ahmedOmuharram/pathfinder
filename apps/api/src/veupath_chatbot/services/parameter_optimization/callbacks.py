"""SSE progress callbacks for parameter optimization.

Each event type is a frozen CamelModel whose ``model_dump(by_alias=True,
mode="json")`` produces the exact SSE shape the frontend expects — no
post-dump dict patching.  The ``emit_*`` helpers just wrap in the standard
SSE envelope (``{"type": "optimization_progress", "data": ...}``).
"""

from typing import Literal

from pydantic import ConfigDict, Field, computed_field

from veupath_chatbot.platform.pydantic_base import CamelModel, RoundedFloat2
from veupath_chatbot.platform.types import JSONArray, JSONObject
from veupath_chatbot.services.parameter_optimization.config import (
    ProgressCallback,
    TrialResult,
)


class OptimizationStartedEvent(CamelModel):
    """Data for an optimization_started SSE event."""

    model_config = ConfigDict(frozen=True)

    type: Literal["optimization_started"] = "optimization_started"
    status: Literal["started"] = "started"
    optimization_id: str
    search_name: str
    record_type: str
    budget: int
    objective: str
    positive_controls_count: int
    negative_controls_count: int
    parameter_space: JSONArray
    best_trial: None = None
    recent_trials: list[TrialResult] = Field(default_factory=list)

    @computed_field
    def current_trial(self) -> int:
        return 0

    @computed_field
    def total_trials(self) -> int:
        return self.budget


class TrialProgressEvent(CamelModel):
    """Data for a trial_progress SSE event."""

    model_config = ConfigDict(frozen=True)

    type: Literal["trial_progress"] = "trial_progress"
    status: Literal["running"] = "running"
    optimization_id: str
    trial_num: int
    budget: int
    trial: TrialResult
    best_trial: TrialResult | None
    recent_trials: list[TrialResult]
    wdk_error: str = Field(default="", exclude=True)

    @computed_field
    def current_trial(self) -> int:
        return self.trial_num

    @computed_field
    def total_trials(self) -> int:
        return self.budget


class OptimizationCompletedEvent(CamelModel):
    """Data for an optimization_completed SSE event."""

    model_config = ConfigDict(frozen=True)

    type: Literal["optimization_completed"] = "optimization_completed"
    optimization_id: str
    status: str
    budget: int
    all_trials: list[TrialResult]
    best_trial: TrialResult | None
    pareto_frontier: list[TrialResult]
    sensitivity: dict[str, float]
    total_time_seconds: RoundedFloat2

    @computed_field
    def current_trial(self) -> int:
        return len(self.all_trials)

    @computed_field
    def total_trials(self) -> int:
        return self.budget


class OptimizationErrorEvent(CamelModel):
    """Data for an optimization_error SSE event."""

    model_config = ConfigDict(frozen=True)

    type: Literal["optimization_error"] = "optimization_error"
    status: Literal["error"] = "error"
    optimization_id: str
    error: str


def _to_sse_envelope(data: JSONObject) -> JSONObject:
    """Wrap event data in the standard SSE envelope."""
    return {"type": "optimization_progress", "data": data}


async def emit_started(
    callback: ProgressCallback,
    event: OptimizationStartedEvent,
) -> None:
    await callback(_to_sse_envelope(event.model_dump(by_alias=True, mode="json")))


async def emit_trial_progress(
    callback: ProgressCallback,
    event: TrialProgressEvent,
) -> None:
    data = event.model_dump(by_alias=True, mode="json")
    # Merge wdk_error into the trial dict if present (excluded from top-level).
    if event.wdk_error:
        trial_dict = data.get("trial")
        if isinstance(trial_dict, dict):
            trial_dict["error"] = event.wdk_error
    await callback(_to_sse_envelope(data))


async def emit_error(
    callback: ProgressCallback,
    *,
    optimization_id: str,
    error: str,
) -> None:
    event = OptimizationErrorEvent(
        optimization_id=optimization_id,
        error=error,
    )
    await callback(_to_sse_envelope(event.model_dump(by_alias=True, mode="json")))


async def emit_completed(
    callback: ProgressCallback,
    event: OptimizationCompletedEvent,
) -> None:
    await callback(_to_sse_envelope(event.model_dump(by_alias=True, mode="json")))
