"""Configuration types for parameter optimization.

Defines the parameter specification, optimization config, trial result,
and optimization result dataclasses, as well as type aliases for callbacks.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

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


@dataclass(frozen=True, slots=True)
class ParameterSpec:
    """Describes a single parameter to optimise."""

    name: str
    param_type: ParameterType
    # numeric / integer
    min_value: float | None = None
    max_value: float | None = None
    log_scale: bool = False
    step: float | None = None
    # categorical
    choices: list[str] | None = None


@dataclass(slots=True)
class OptimizationConfig:
    budget: int = 30
    objective: OptimizationObjective = "f1"
    beta: float = 1.0  # only for f_beta
    recall_weight: float = 1.0  # only for custom
    precision_weight: float = 1.0  # only for custom
    method: OptimizationMethod = "bayesian"
    result_count_penalty: float = 0.0
    """Weight for penalising large result sets.  The penalty is
    ``result_count_penalty * (result_count / total_genes)`` where
    *total_genes* is the denominator (defaults to 20 000 if unknown).
    A small value (e.g. 0.1) acts as a tiebreaker; higher values make
    the optimiser strongly prefer tighter results."""


@dataclass(frozen=True, slots=True)
class TrialResult:
    trial_number: int
    parameters: dict[str, JSONValue]
    score: float
    recall: float | None
    false_positive_rate: float | None
    result_count: int | None
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


@dataclass(slots=True)
class OptimizationResult:
    optimization_id: str
    best_trial: TrialResult | None
    all_trials: list[TrialResult]
    pareto_frontier: list[TrialResult]
    sensitivity: dict[str, float]
    total_time_seconds: float
    status: str  # completed | cancelled | error
    error_message: str | None = None
