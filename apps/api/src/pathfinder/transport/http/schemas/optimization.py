"""Optimization event/response models shared by chat and SSE schemas."""

from pydantic import Field, JsonValue

from pathfinder.platform.pydantic_base import CamelModel


class OptimizationTrialData(CamelModel):
    """A single optimization trial result."""

    trial_number: int
    parameters: dict[str, JsonValue] = Field(default_factory=dict)
    score: float = 0.0
    recall: float | None = None
    false_positive_rate: float | None = Field(default=None)
    estimated_size: int | None = Field(default=None)
    positive_hits: int | None = Field(default=None)
    negative_hits: int | None = Field(default=None)
    total_positives: int | None = Field(default=None)
    total_negatives: int | None = Field(default=None)


class OptimizationParameterSpecData(CamelModel):
    """Specification for one optimization parameter."""

    name: str
    type: str
    min: float | None = None
    max: float | None = None
    log_scale: bool | None = Field(default=None)
    choices: list[str] | None = None


class OptimizationProgressEventData(CamelModel):
    """Payload for ``optimization_progress`` SSE events."""

    optimization_id: str
    status: str = ""
    search_name: str | None = Field(default=None)
    record_type: str | None = Field(default=None)
    budget: int | None = None
    objective: str | None = None
    current_trial: int | None = Field(default=None)
    total_trials: int | None = Field(default=None)
    parameter_specs: list[OptimizationParameterSpecData] | None = Field(default=None)
    trial: OptimizationTrialData | None = None
    best_trial: OptimizationTrialData | None = Field(default=None)
    recent_trials: list[OptimizationTrialData] | None = Field(default=None)
    all_trials: list[OptimizationTrialData] | None = Field(default=None)
    pareto_frontier: list[OptimizationTrialData] | None = Field(default=None)
    sensitivity: dict[str, float] | None = None
    total_time_seconds: float | None = Field(default=None)
    error: str | None = None

