"""Experiment Lab request/response DTOs."""

from typing import Literal

from pydantic import Field, JsonValue

from pathfinder.domain.parameters.values import ParamValue
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.platform.types import JSONObject
from pathfinder.services.experiment.types import (
    ControlValueFormat,
    EnrichmentAnalysisType,
    ExperimentMode,
    OptimizationObjective,
)
from pathfinder.services.wdk import WDKSortDirection


class ThresholdKnobRequest(CamelModel):
    """A numeric parameter knob for tree optimization."""

    step_id: str
    param_name: str
    min_val: float = Field(default=0)
    max_val: float = Field(default=1)
    step_size: float | None = Field(default=None)


class OperatorKnobRequest(CamelModel):
    """A boolean-operator knob for tree optimization."""

    combine_node_id: str
    options: list[str] = Field(default_factory=lambda: ["INTERSECT", "UNION", "MINUS"])


class OptimizationSpecRequest(CamelModel):
    """Describes a single parameter to optimise."""

    name: str
    type: Literal["numeric", "integer", "categorical"]
    min: float | None = None
    max: float | None = None
    step: float | None = None
    choices: list[str] | None = None


class CreateExperimentRequest(CamelModel):
    """Request to create and run an experiment.

    Supports three modes: ``single`` (default), ``multi-step``, and ``import``.
    """

    site_id: str
    record_type: str
    mode: ExperimentMode = Field(default="single")
    search_name: str = Field(default="")
    parameters: dict[str, ParamValue] = Field(default_factory=dict)
    step_tree: JsonValue = Field(default=None)
    source_strategy_id: str | None = Field(default=None)
    optimization_target_step: str | None = Field(default=None)
    positive_controls: list[str]
    negative_controls: list[str]
    controls_search_name: str
    controls_param_name: str
    controls_value_format: ControlValueFormat = Field(default="newline")
    enable_cross_validation: bool = Field(default=False)
    k_folds: int = Field(default=5, ge=2, le=10)
    enrichment_types: list[EnrichmentAnalysisType] = Field(default_factory=list)
    name: str = Field(default="Untitled Experiment", max_length=200)
    description: str = Field(default="", max_length=2000)
    optimization_specs: list[OptimizationSpecRequest] | None = Field(default=None)
    optimization_budget: int = Field(default=30, ge=5, le=200)
    optimization_objective: OptimizationObjective | None = Field(default=None)
    parameter_display_values: JSONObject | None = Field(default=None)
    enable_step_analysis: bool = Field(default=False)
    step_analysis_phases: list[str] | None = Field(default=None)
    control_set_id: str | None = Field(default=None)
    threshold_knobs: list[ThresholdKnobRequest] | None = Field(default=None)
    operator_knobs: list[OperatorKnobRequest] | None = Field(default=None)
    tree_optimization_objective: str = Field(default="precision_at_50")
    tree_optimization_budget: int = Field(default=50, ge=5, le=200)
    max_list_size: int | None = Field(default=None)
    sort_attribute: str | None = Field(default=None)
    sort_direction: WDKSortDirection = Field(default="ASC")
    parent_experiment_id: str | None = Field(default=None)
    target_gene_ids: list[str] | None = Field(default=None)


class BatchOrganismTargetRequest(CamelModel):
    """Per-organism override for a cross-organism batch experiment."""

    organism: str
    positive_controls: list[str] | None = Field(default=None)
    negative_controls: list[str] | None = Field(default=None)


class CreateBatchExperimentRequest(CamelModel):
    """Request to run the same search across multiple organisms."""

    base: CreateExperimentRequest
    organism_param_name: str
    target_organisms: list[BatchOrganismTargetRequest] = Field(min_length=1)


class RunCrossValidationRequest(CamelModel):
    """Request to run cross-validation on an existing experiment."""

    k_folds: int = Field(default=5, ge=2, le=10)


class RunEnrichmentRequest(CamelModel):
    """Request to run enrichment on an existing experiment."""

    enrichment_types: list[EnrichmentAnalysisType]


class ThresholdSweepRequest(CamelModel):
    """Request to sweep a parameter across a range (numeric) or set of values (categorical)."""

    parameter_name: str
    sweep_type: Literal["numeric", "categorical"] = Field(default="numeric")
    min: float | None = None
    max: float | None = None
    steps: int = Field(default=10, ge=3, le=50)
    values: list[str] | None = Field(default=None)


class RefineRequest(CamelModel):
    """Request to refine an experiment's strategy."""

    action: Literal["combine", "transform"]
    search_name: str = Field(default="")
    parameters: dict[str, ParamValue] = Field(default_factory=dict)
    operator: str = Field(default="INTERSECT")
    transform_name: str = Field(default="")


class RefineResponse(CamelModel):
    """Response from refine_experiment."""

    success: bool
    new_step_id: int | None = Field(default=None)


class CustomEnrichRequest(CamelModel):
    """Request to run a custom gene-set enrichment test."""

    gene_set_name: str = Field(min_length=1)
    gene_ids: list[str] = Field(min_length=1)


class BenchmarkControlSet(CamelModel):
    """A single control set within a benchmark suite."""

    label: str = Field(min_length=1)
    positive_controls: list[str]
    negative_controls: list[str]
    control_set_id: str | None = Field(default=None)
    is_primary: bool = Field(default=False)


class CreateBenchmarkRequest(CamelModel):
    """Request to run a benchmark suite across multiple control sets."""

    base: CreateExperimentRequest
    control_sets: list[BenchmarkControlSet] = Field(min_length=1)


class OverlapRequest(CamelModel):
    """Request to compute pairwise gene set overlap between experiments."""

    experiment_ids: list[str] = Field(min_length=2)


class EnrichmentCompareRequest(CamelModel):
    """Request to compare enrichment results across experiments."""

    experiment_ids: list[str] = Field(min_length=2)
    analysis_type: str | None = Field(default=None)
