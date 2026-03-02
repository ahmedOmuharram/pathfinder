"""Optimization-related dataclasses for the Experiment Lab."""

from __future__ import annotations

from dataclasses import dataclass, field

from veupath_chatbot.services.experiment.types.core import (
    ControlSetSource,
    ParameterType,
)
from veupath_chatbot.services.experiment.types.rank import RankMetrics


@dataclass(slots=True)
class OptimizationSpec:
    """Describes a single parameter to optimise."""

    name: str
    type: ParameterType
    min: float | None = None
    max: float | None = None
    step: float | None = None
    choices: list[str] | None = None


@dataclass(frozen=True, slots=True)
class ControlSetSummary:
    """Lightweight control set reference for experiment configs."""

    id: str
    name: str
    source: ControlSetSource
    tags: list[str] = field(default_factory=list)
    positive_count: int = 0
    negative_count: int = 0


@dataclass(frozen=True, slots=True)
class ThresholdKnob:
    """A numeric parameter on a leaf step that can be tuned."""

    step_id: str
    param_name: str
    min_val: float
    max_val: float
    step_size: float | None = None


@dataclass(frozen=True, slots=True)
class OperatorKnob:
    """A combine-node operator that can be switched during optimization."""

    combine_node_id: str
    options: list[str] = field(default_factory=lambda: ["INTERSECT", "UNION", "MINUS"])


@dataclass(frozen=True, slots=True)
class TreeOptimizationTrial:
    """One trial during tree-knob optimization."""

    trial_number: int
    parameters: dict[str, float | str]
    score: float
    rank_metrics: RankMetrics | None = None
    list_size: int = 0


@dataclass(frozen=True, slots=True)
class TreeOptimizationResult:
    """Result of multi-step tree-knob optimization."""

    best_trial: TreeOptimizationTrial | None = None
    all_trials: list[TreeOptimizationTrial] = field(default_factory=list)
    total_time_seconds: float = 0.0
    objective: str = ""
