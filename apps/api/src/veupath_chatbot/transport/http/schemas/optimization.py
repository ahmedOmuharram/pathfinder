"""Optimization event/response models shared by chat and SSE schemas."""

from pydantic import BaseModel, Field

from veupath_chatbot.platform.types import JSONValue


class OptimizationTrialData(BaseModel):
    """A single optimization trial result."""

    trial_number: int = Field(alias="trialNumber")
    parameters: dict[str, JSONValue] = Field(default_factory=dict)
    score: float = 0.0
    recall: float | None = None
    false_positive_rate: float | None = Field(default=None, alias="falsePositiveRate")
    estimated_size: int | None = Field(default=None, alias="estimatedSize")
    positive_hits: int | None = Field(default=None, alias="positiveHits")
    negative_hits: int | None = Field(default=None, alias="negativeHits")
    total_positives: int | None = Field(default=None, alias="totalPositives")
    total_negatives: int | None = Field(default=None, alias="totalNegatives")

    model_config = {"populate_by_name": True}


class OptimizationParameterSpecData(BaseModel):
    """Specification for one optimization parameter."""

    name: str
    type: str
    min_value: float | None = Field(default=None, alias="minValue")
    max_value: float | None = Field(default=None, alias="maxValue")
    log_scale: bool | None = Field(default=None, alias="logScale")
    choices: list[str] | None = None

    model_config = {"populate_by_name": True}


class OptimizationProgressEventData(BaseModel):
    """Payload for ``optimization_progress`` SSE events."""

    optimization_id: str = Field(alias="optimizationId")
    status: str = ""
    search_name: str | None = Field(default=None, alias="searchName")
    record_type: str | None = Field(default=None, alias="recordType")
    budget: int | None = None
    objective: str | None = None
    current_trial: int | None = Field(default=None, alias="currentTrial")
    total_trials: int | None = Field(default=None, alias="totalTrials")
    parameter_specs: list[OptimizationParameterSpecData] | None = Field(
        default=None, alias="parameterSpecs"
    )
    trial: OptimizationTrialData | None = None
    best_trial: OptimizationTrialData | None = Field(default=None, alias="bestTrial")
    recent_trials: list[OptimizationTrialData] | None = Field(
        default=None, alias="recentTrials"
    )
    all_trials: list[OptimizationTrialData] | None = Field(
        default=None, alias="allTrials"
    )
    pareto_frontier: list[OptimizationTrialData] | None = Field(
        default=None, alias="paretoFrontier"
    )
    sensitivity: dict[str, float] | None = None
    total_time_seconds: float | None = Field(default=None, alias="totalTimeSeconds")
    error: str | None = None

    model_config = {"populate_by_name": True}
