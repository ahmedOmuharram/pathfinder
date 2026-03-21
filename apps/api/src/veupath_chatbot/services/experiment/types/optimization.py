"""Optimization-related types for the Experiment Lab."""

from pydantic import ConfigDict, Field

from veupath_chatbot.platform.pydantic_base import (
    CamelModel,
    RoundedFloat,
    RoundedFloat2,
)
from veupath_chatbot.services.experiment.types.core import ParameterType
from veupath_chatbot.services.experiment.types.rank import RankMetrics


class OptimizationSpec(CamelModel):
    """Describes a single parameter to optimise."""

    name: str
    type: ParameterType
    min: float | None = None
    max: float | None = None
    step: float | None = None
    choices: list[str] | None = None


class ThresholdKnob(CamelModel):
    """A numeric parameter on a leaf step that can be tuned."""

    model_config = ConfigDict(frozen=True)

    step_id: str
    param_name: str
    min_val: float
    max_val: float
    step_size: float | None = None


class OperatorKnob(CamelModel):
    """A combine-node operator that can be switched during optimization."""

    model_config = ConfigDict(frozen=True)

    combine_node_id: str
    options: list[str] = Field(default_factory=lambda: ["INTERSECT", "UNION", "MINUS"])


class TreeOptimizationTrial(CamelModel):
    """One trial during tree-knob optimization."""

    model_config = ConfigDict(frozen=True)

    trial_number: int
    parameters: dict[str, float | str] = Field(default_factory=dict)
    score: RoundedFloat = 0.0
    rank_metrics: RankMetrics | None = None
    list_size: int = 0


class TreeOptimizationResult(CamelModel):
    """Result of multi-step tree-knob optimization."""

    model_config = ConfigDict(frozen=True)

    best_trial: TreeOptimizationTrial | None = None
    all_trials: list[TreeOptimizationTrial] = Field(default_factory=list)
    total_time_seconds: RoundedFloat2 = 0.0
    objective: str = ""
