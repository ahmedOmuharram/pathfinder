"""Step request/response DTOs."""

from __future__ import annotations

from pydantic import BaseModel, Field

from veupath_chatbot.platform.types import JSONObject, JSONValue


class StepFilterResponse(BaseModel):
    """Filter attached to a step."""

    name: str
    value: JSONValue
    disabled: bool = False


class StepFiltersResponse(BaseModel):
    """Container for step filters."""

    filters: list[StepFilterResponse]


class StepAnalysisResponse(BaseModel):
    """Analysis configuration attached to a step."""

    analysis_type: str = Field(alias="analysisType")
    parameters: JSONObject = Field(default_factory=dict)
    custom_name: str | None = Field(default=None, alias="customName")

    model_config = {"populate_by_name": True}


class StepReportResponse(BaseModel):
    """Report configuration attached to a step."""

    report_name: str = Field(default="standard", alias="reportName")
    config: JSONObject = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


class StepAnalysisRunResponse(BaseModel):
    """Result of running a step analysis."""

    analysis: StepAnalysisResponse
    wdk: JSONObject | None = None


class StepReportRunResponse(BaseModel):
    """Result of running a step report."""

    report: StepReportResponse
    wdk: JSONObject | None = None


class StepResponse(BaseModel):
    """Strategy step."""

    id: str
    kind: str | None = None
    display_name: str = Field(alias="displayName")
    search_name: str | None = Field(default=None, alias="searchName")
    record_type: str | None = Field(default=None, alias="recordType")
    parameters: JSONObject | None = None
    operator: str | None = None
    colocation_params: JSONObject | None = Field(default=None, alias="colocationParams")
    primary_input_step_id: str | None = Field(default=None, alias="primaryInputStepId")
    secondary_input_step_id: str | None = Field(
        default=None, alias="secondaryInputStepId"
    )
    result_count: int | None = Field(default=None, alias="resultCount")
    wdk_step_id: int | None = Field(default=None, alias="wdkStepId")
    filters: list[StepFilterResponse] | None = None
    analyses: list[StepAnalysisResponse] | None = None
    reports: list[StepReportResponse] | None = None

    model_config = {"populate_by_name": True}


class StepFilterRequest(BaseModel):
    """Request to set or update a step filter."""

    value: JSONValue
    disabled: bool = False


class StepAnalysisRequest(BaseModel):
    """Request to run a step analysis."""

    analysis_type: str = Field(alias="analysisType")
    parameters: JSONObject = Field(default_factory=dict)
    custom_name: str | None = Field(default=None, alias="customName")

    model_config = {"populate_by_name": True}


class StepReportRequest(BaseModel):
    """Request to run a step report."""

    report_name: str = Field(default="standard", alias="reportName")
    config: JSONObject = Field(default_factory=dict)

    model_config = {"populate_by_name": True}
