"""Experiment Lab request/response DTOs."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from veupath_chatbot.platform.types import JSONArray, JSONObject

WizardStepLiteral = Literal["search", "parameters", "controls", "run"]

EnrichmentAnalysisType = Literal[
    "go_function", "go_component", "go_process", "pathway", "word"
]


class CreateExperimentRequest(BaseModel):
    """Request to create and run an experiment."""

    site_id: str = Field(alias="siteId")
    record_type: str = Field(alias="recordType")
    search_name: str = Field(alias="searchName")
    parameters: JSONObject = Field(default_factory=dict)
    positive_controls: list[str] = Field(alias="positiveControls")
    negative_controls: list[str] = Field(alias="negativeControls")
    controls_search_name: str = Field(alias="controlsSearchName")
    controls_param_name: str = Field(alias="controlsParamName")
    controls_value_format: str = Field(default="newline", alias="controlsValueFormat")
    enable_cross_validation: bool = Field(default=False, alias="enableCrossValidation")
    k_folds: int = Field(default=5, alias="kFolds", ge=2, le=10)
    enrichment_types: list[EnrichmentAnalysisType] = Field(
        default_factory=list, alias="enrichmentTypes"
    )
    name: str = Field(default="Untitled Experiment", max_length=200)
    description: str = Field(default="", max_length=2000)

    model_config = {"populate_by_name": True}


class RunCrossValidationRequest(BaseModel):
    """Request to run cross-validation on an existing experiment."""

    k_folds: int = Field(default=5, alias="kFolds", ge=2, le=10)

    model_config = {"populate_by_name": True}


class RunEnrichmentRequest(BaseModel):
    """Request to run enrichment on an existing experiment."""

    enrichment_types: list[EnrichmentAnalysisType] = Field(alias="enrichmentTypes")

    model_config = {"populate_by_name": True}


class ExperimentSummaryResponse(BaseModel):
    """Lightweight experiment summary."""

    id: str
    name: str
    site_id: str = Field(alias="siteId")
    search_name: str = Field(alias="searchName")
    record_type: str = Field(alias="recordType")
    status: str
    f1_score: float | None = Field(default=None, alias="f1Score")
    sensitivity: float | None = None
    specificity: float | None = None
    total_positives: int = Field(alias="totalPositives")
    total_negatives: int = Field(alias="totalNegatives")
    created_at: str = Field(alias="createdAt")

    model_config = {"populate_by_name": True}


class AiAssistRequest(BaseModel):
    """Request for the experiment wizard AI assistant."""

    site_id: str = Field(alias="siteId")
    step: WizardStepLiteral
    message: str = Field(min_length=1, max_length=50_000)
    context: JSONObject = Field(default_factory=dict)
    history: JSONArray = Field(default_factory=list)
    model: str | None = Field(default=None)

    model_config = {"populate_by_name": True}
