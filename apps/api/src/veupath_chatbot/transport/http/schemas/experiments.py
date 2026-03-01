"""Experiment Lab request/response DTOs."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from veupath_chatbot.platform.types import JSONArray, JSONObject, JSONValue
from veupath_chatbot.services.experiment.types import (
    ControlValueFormat,
    EnrichmentAnalysisType,
    ExperimentMode,
    OptimizationObjective,
    WizardStep,
)


class ThresholdKnobRequest(BaseModel):
    """A numeric parameter knob for tree optimization."""

    step_id: str = Field(alias="stepId")
    param_name: str = Field(alias="paramName")
    min_val: float = Field(alias="minVal", default=0)
    max_val: float = Field(alias="maxVal", default=1)
    step_size: float | None = Field(alias="stepSize", default=None)

    model_config = {"populate_by_name": True}


class OperatorKnobRequest(BaseModel):
    """A boolean-operator knob for tree optimization."""

    combine_node_id: str = Field(alias="combineNodeId")
    options: list[str] = Field(default_factory=lambda: ["INTERSECT", "UNION", "MINUS"])

    model_config = {"populate_by_name": True}


class OptimizationSpecRequest(BaseModel):
    """Describes a single parameter to optimise."""

    name: str
    type: Literal["numeric", "integer", "categorical"]
    min: float | None = None
    max: float | None = None
    step: float | None = None
    choices: list[str] | None = None


class CreateExperimentRequest(BaseModel):
    """Request to create and run an experiment.

    Supports three modes: ``single`` (default), ``multi-step``, and ``import``.
    """

    site_id: str = Field(alias="siteId")
    record_type: str = Field(alias="recordType")
    mode: ExperimentMode = Field(default="single")
    search_name: str = Field(default="", alias="searchName")
    parameters: JSONObject = Field(default_factory=dict)
    step_tree: JSONValue = Field(default=None, alias="stepTree")
    source_strategy_id: str | None = Field(default=None, alias="sourceStrategyId")
    optimization_target_step: str | None = Field(
        default=None, alias="optimizationTargetStep"
    )
    positive_controls: list[str] = Field(alias="positiveControls")
    negative_controls: list[str] = Field(alias="negativeControls")
    controls_search_name: str = Field(alias="controlsSearchName")
    controls_param_name: str = Field(alias="controlsParamName")
    controls_value_format: ControlValueFormat = Field(
        default="newline", alias="controlsValueFormat"
    )
    enable_cross_validation: bool = Field(default=False, alias="enableCrossValidation")
    k_folds: int = Field(default=5, alias="kFolds", ge=2, le=10)
    enrichment_types: list[EnrichmentAnalysisType] = Field(
        default_factory=list, alias="enrichmentTypes"
    )
    name: str = Field(default="Untitled Experiment", max_length=200)
    description: str = Field(default="", max_length=2000)
    optimization_specs: list[OptimizationSpecRequest] | None = Field(
        default=None, alias="optimizationSpecs"
    )
    optimization_budget: int = Field(
        default=30, alias="optimizationBudget", ge=5, le=200
    )
    optimization_objective: OptimizationObjective | None = Field(
        default=None, alias="optimizationObjective"
    )
    parameter_display_values: JSONObject | None = Field(
        default=None, alias="parameterDisplayValues"
    )
    enable_step_analysis: bool = Field(default=False, alias="enableStepAnalysis")
    step_analysis_phases: list[str] | None = Field(
        default=None, alias="stepAnalysisPhases"
    )
    control_set_id: str | None = Field(default=None, alias="controlSetId")
    threshold_knobs: list[ThresholdKnobRequest] | None = Field(
        default=None, alias="thresholdKnobs"
    )
    operator_knobs: list[OperatorKnobRequest] | None = Field(
        default=None, alias="operatorKnobs"
    )
    tree_optimization_objective: str = Field(
        default="precision_at_50", alias="treeOptimizationObjective"
    )
    tree_optimization_budget: int = Field(
        default=50, alias="treeOptimizationBudget", ge=5, le=200
    )
    max_list_size: int | None = Field(default=None, alias="maxListSize")
    sort_attribute: str | None = Field(default=None, alias="sortAttribute")
    sort_direction: Literal["ASC", "DESC"] = Field(default="ASC", alias="sortDirection")
    parent_experiment_id: str | None = Field(default=None, alias="parentExperimentId")
    model_config = {"populate_by_name": True}


class BatchOrganismTargetRequest(BaseModel):
    """Per-organism override for a cross-organism batch experiment."""

    organism: str
    positive_controls: list[str] = Field(default_factory=list, alias="positiveControls")
    negative_controls: list[str] = Field(default_factory=list, alias="negativeControls")

    model_config = {"populate_by_name": True}


class CreateBatchExperimentRequest(BaseModel):
    """Request to run the same search across multiple organisms."""

    base: CreateExperimentRequest
    organism_param_name: str = Field(alias="organismParamName")
    target_organisms: list[BatchOrganismTargetRequest] = Field(
        alias="targetOrganisms", min_length=1
    )

    model_config = {"populate_by_name": True}


class RunCrossValidationRequest(BaseModel):
    """Request to run cross-validation on an existing experiment."""

    k_folds: int = Field(default=5, alias="kFolds", ge=2, le=10)

    model_config = {"populate_by_name": True}


class RunEnrichmentRequest(BaseModel):
    """Request to run enrichment on an existing experiment."""

    enrichment_types: list[EnrichmentAnalysisType] = Field(alias="enrichmentTypes")

    model_config = {"populate_by_name": True}


class ThresholdSweepRequest(BaseModel):
    """Request to sweep a numeric parameter across a range."""

    parameter_name: str = Field(alias="parameterName")
    min_value: float = Field(alias="minValue")
    max_value: float = Field(alias="maxValue")
    steps: int = Field(default=10, ge=3, le=50)

    model_config = {"populate_by_name": True}


class RunAnalysisRequest(BaseModel):
    """Request to run a WDK step analysis."""

    analysis_name: str = Field(alias="analysisName", min_length=1)
    parameters: JSONObject = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


class RefineRequest(BaseModel):
    """Request to refine an experiment's strategy."""

    action: Literal["combine", "transform"]
    search_name: str = Field(default="", alias="searchName")
    parameters: JSONObject = Field(default_factory=dict)
    operator: str = Field(default="INTERSECT")
    transform_name: str = Field(default="", alias="transformName")

    model_config = {"populate_by_name": True}


class CustomEnrichRequest(BaseModel):
    """Request to run a custom gene-set enrichment test."""

    gene_set_name: str = Field(alias="geneSetName", min_length=1)
    gene_ids: list[str] = Field(alias="geneIds", min_length=1)

    model_config = {"populate_by_name": True}


class BenchmarkControlSet(BaseModel):
    """A single control set within a benchmark suite."""

    label: str = Field(min_length=1)
    positive_controls: list[str] = Field(alias="positiveControls")
    negative_controls: list[str] = Field(alias="negativeControls")
    control_set_id: str | None = Field(default=None, alias="controlSetId")
    is_primary: bool = Field(default=False, alias="isPrimary")

    model_config = {"populate_by_name": True}


class CreateBenchmarkRequest(BaseModel):
    """Request to run a benchmark suite across multiple control sets."""

    base: CreateExperimentRequest
    control_sets: list[BenchmarkControlSet] = Field(alias="controlSets", min_length=1)

    model_config = {"populate_by_name": True}


class OverlapRequest(BaseModel):
    """Request to compute pairwise gene set overlap between experiments."""

    experiment_ids: list[str] = Field(alias="experimentIds", min_length=2)

    model_config = {"populate_by_name": True}


class EnrichmentCompareRequest(BaseModel):
    """Request to compare enrichment results across experiments."""

    experiment_ids: list[str] = Field(alias="experimentIds", min_length=2)
    analysis_type: str | None = Field(default=None, alias="analysisType")

    model_config = {"populate_by_name": True}


class AiAssistRequest(BaseModel):
    """Request for the experiment wizard AI assistant."""

    site_id: str = Field(alias="siteId")
    step: WizardStep
    message: str = Field(min_length=1, max_length=50_000)
    context: JSONObject = Field(default_factory=dict)
    history: JSONArray = Field(default_factory=list)
    model: str | None = Field(default=None)

    model_config = {"populate_by_name": True}
