"""Configuration types for parameter optimization.

Defines the parameter specification, optimization config, trial result,
and optimization result types, as well as type aliases for callbacks.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from veupath_chatbot.platform.pydantic_base import (
    CamelModel,
    RoundedFloat,
    RoundedFloat2,
)
from veupath_chatbot.platform.types import JSONObject, JSONValue
from veupath_chatbot.services.experiment.helpers import ProgressCallback
from veupath_chatbot.services.experiment.types import (
    ControlValueFormat,
    OptimizationObjective,
    ParameterType,
)

__all__ = ["ProgressCallback"]  # re-exported for parameter_optimization consumers


CancelCheck = Callable[[], bool]
"""Returns True when the optimisation should stop early."""

OptimizationMethod = Literal["bayesian", "grid", "random"]


class ParameterSpec(BaseModel):
    """Describes a single parameter to optimise.

    Accepts both JSON aliases (``type``, ``min``, ``max``, ``logScale``)
    and Python field names (``param_type``, ``min_value``, ``max_value``,
    ``log_scale``) so the same model works for LLM JSON input and
    programmatic construction.
    """

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    name: str = Field(min_length=1)
    param_type: ParameterType = Field(alias="type")
    # numeric / integer
    min_value: float | None = Field(None, alias="min")
    max_value: float | None = Field(None, alias="max")
    log_scale: bool = Field(default=False, alias="logScale")
    step: float | None = None
    # categorical
    choices: list[str] | None = None

    @model_validator(mode="after")
    def _validate_constraints(self) -> Self:
        """Validate logical consistency of fields.

        Only checks constraints that would be *logically wrong* regardless of
        context (min >= max, step <= 0).  The stricter "min/max required for
        numeric" rule is enforced by :func:`_parse_parameter_space` during LLM
        JSON parsing, since internal code may construct specs with ``None``
        bounds and rely on runtime defaults.
        """
        if (
            self.min_value is not None
            and self.max_value is not None
            and self.min_value >= self.max_value
        ):
            msg = (
                f"'min' ({self.min_value}) must be strictly less than "
                f"'max' ({self.max_value})"
            )
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
    parameters: dict[str, JSONValue]
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
    fixed_parameters: dict[str, JSONValue] = field(default_factory=dict)
    positive_controls: list[str] | None = None
    negative_controls: list[str] | None = None
    controls_value_format: ControlValueFormat = "newline"
    controls_extra_parameters: JSONObject | None = None
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

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_trials(self) -> int:
        """Number of trials (derived from all_trials)."""
        return len(self.all_trials)
