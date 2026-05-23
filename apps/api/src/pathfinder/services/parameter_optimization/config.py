"""Configuration types for parameter optimization.

Defines the parameter specification, optimization config, trial result,
and optimization result types, as well as type aliases for callbacks.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal, Self

from pydantic import ConfigDict, Field, model_validator

from pathfinder.domain.parameters.values import ParamValue
from pathfinder.platform.pydantic_base import (
    CamelModel,
    RoundedFloat,
    RoundedFloat2,
)
from pathfinder.services.experiment.helpers import ProgressCallback
from pathfinder.services.experiment.types import (
    ControlValueFormat,
    OptimizationObjective,
    ParameterType,
)

__all__ = ["ProgressCallback"]  # re-exported for parameter_optimization consumers

CancelCheck = Callable[[], bool]
"""Returns True when the optimisation should stop early."""

OptimizationMethod = Literal["bayesian", "grid", "random"]

class ParameterSpec(CamelModel):
    """Describes a single parameter to optimise. Field names match WDK wire."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    param_type: ParameterType = Field(alias="type")
    min: float | None = None
    max: float | None = None
    log_scale: bool = False
    step: float | None = None
    choices: list[str] | None = None

    @model_validator(mode="after")
    def _validate_constraints(self) -> Self:
        if (
            self.min is not None
            and self.max is not None
            and self.min >= self.max
        ):
            msg = f"'min' ({self.min}) must be strictly less than 'max' ({self.max})"
            raise ValueError(msg)
        if self.step is not None and self.step <= 0:
            msg = f"'step' must be positive, got {self.step}"
            raise ValueError(msg)
        return self

@dataclass(slots=True)
class OptimizationConfig:
    budget: int = 30
    objective: OptimizationObjective = "f1"
    beta: float = 1.0  # only for f_beta
    recall_weight: float = 1.0  # only for custom
    precision_weight: float = 1.0  # only for custom
    method: OptimizationMethod = "bayesian"
    estimated_size_penalty: float = 0.0
    """Weight for penalising large result sets.  The penalty is
    ``estimated_size_penalty * (estimated_size / total_genes)`` where
    *total_genes* is the denominator (defaults to 20 000 if unknown).
    A small value (e.g. 0.1) acts as a tiebreaker; higher values make
    the optimiser strongly prefer tighter results."""

class TrialResult(CamelModel):
    """A single optimization trial result.

    Frozen CamelModel — serializes to camelCase with RoundedFloat (4 dp)
    for score/recall/fpr fields.
    """

    model_config = ConfigDict(frozen=True)

    trial_number: int
    parameters: dict[str, ParamValue]
    score: RoundedFloat
    recall: RoundedFloat | None
    false_positive_rate: RoundedFloat | None
    estimated_size: int | None
    positive_hits: int | None = None
    negative_hits: int | None = None
    total_positives: int | None = None
    total_negatives: int | None = None

@dataclass
class OptimizationInput:
    """What to optimize: target search, controls, and parameter space."""

    site_id: str
    record_type: str
    search_name: str
    parameter_space: list[ParameterSpec]
    controls_search_name: str
    controls_param_name: str
    fixed_parameters: dict[str, ParamValue] = field(default_factory=dict)
    positive_controls: list[str] | None = None
    negative_controls: list[str] | None = None
    controls_value_format: ControlValueFormat = "newline"
    controls_extra_parameters: dict[str, ParamValue] | None = None
    id_field: str | None = None

class OptimizationResult(CamelModel):
    """Full optimization result.

    CamelModel — serializes to camelCase.  ``total_trials`` is computed
    from ``len(all_trials)`` so callers never need to pass it explicitly.
    """

    optimization_id: str
    best_trial: TrialResult | None
    all_trials: list[TrialResult]
    pareto_frontier: list[TrialResult]
    sensitivity: dict[str, float]
    total_time_seconds: RoundedFloat2
    status: str  # completed | cancelled | error
    error_message: str | None = None
    total_trials: int = 0

    @model_validator(mode="after")
    def _compute_total_trials(self) -> Self:
        """Derive total_trials from all_trials at construction time."""
        self.total_trials = len(self.all_trials)
        return self
