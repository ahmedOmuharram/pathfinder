"""Request/response DTOs for HTTP routes."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, RootModel


# ============================================================================
# Health
# ============================================================================


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    timestamp: datetime


# ============================================================================
# Sites
# ============================================================================


class SiteResponse(BaseModel):
    """VEuPathDB site information."""

    id: str
    name: str
    display_name: str = Field(alias="displayName")
    base_url: str = Field(alias="baseUrl")
    project_id: str = Field(alias="projectId")
    is_portal: bool = Field(alias="isPortal")

    model_config = {"populate_by_name": True}


class RecordTypeResponse(BaseModel):
    """Record type information."""

    name: str
    display_name: str = Field(alias="displayName")
    description: str | None = None

    model_config = {"populate_by_name": True}


class SearchResponse(BaseModel):
    """Search information."""

    name: str
    display_name: str = Field(alias="displayName")
    description: str | None = None
    record_type: str = Field(alias="recordType")

    model_config = {"populate_by_name": True}


class DependentParamsRequest(BaseModel):
    """Dependent parameter values request."""

    parameter_name: str = Field(alias="parameterName")
    context_values: dict[str, Any] = Field(default_factory=dict, alias="contextValues")

    model_config = {"populate_by_name": True}


class SearchDetailsResponse(BaseModel):
    """Search details payload (UI-facing)."""

    search_data: dict[str, Any] | None = Field(default=None, alias="searchData")
    validation: dict[str, Any] | None = None
    search_config: dict[str, Any] | None = Field(default=None, alias="searchConfig")
    parameters: list[dict[str, Any]] | None = None
    param_map: dict[str, Any] | None = Field(default=None, alias="paramMap")
    question: dict[str, Any] | None = None

    model_config = {"populate_by_name": True, "extra": "allow"}


class DependentParamsResponse(RootModel[list[dict[str, Any]]]):
    """Dependent parameter values response."""


class SearchValidationRequest(BaseModel):
    """Search parameter validation request."""

    context_values: dict[str, Any] = Field(default_factory=dict, alias="contextValues")

    model_config = {"populate_by_name": True}


# ============================================================================
# Chat
# ============================================================================


class ChatRequest(BaseModel):
    """Request to send a chat message."""

    strategy_id: UUID | None = Field(default=None, alias="strategyId")
    site_id: str = Field(alias="siteId")
    message: str = Field(min_length=1, max_length=10000)

    model_config = {"populate_by_name": True}


class ToolCallResponse(BaseModel):
    """Tool call information."""

    id: str
    name: str
    arguments: dict[str, Any]
    result: str | None = None


class SubKaniActivityResponse(BaseModel):
    """Sub-kani tool call activity."""

    calls: dict[str, list[ToolCallResponse]]
    status: dict[str, str]


class ThinkingResponse(BaseModel):
    """In-progress tool call state."""

    tool_calls: list[ToolCallResponse] | None = Field(default=None, alias="toolCalls")
    sub_kani_calls: dict[str, list[ToolCallResponse]] | None = Field(
        default=None, alias="subKaniCalls"
    )
    sub_kani_status: dict[str, str] | None = Field(
        default=None, alias="subKaniStatus"
    )
    updated_at: datetime | None = Field(default=None, alias="updatedAt")

    model_config = {"populate_by_name": True}


class MessageResponse(BaseModel):
    """Chat message."""

    role: str
    content: str
    tool_calls: list[ToolCallResponse] | None = Field(default=None, alias="toolCalls")
    sub_kani_activity: SubKaniActivityResponse | None = Field(
        default=None, alias="subKaniActivity"
    )
    timestamp: datetime

    model_config = {"populate_by_name": True}


# ============================================================================
# Strategies
# ============================================================================


class StepResponse(BaseModel):
    """Strategy step."""

    id: str
    type: str
    display_name: str = Field(alias="displayName")
    search_name: str | None = Field(default=None, alias="searchName")
    transform_name: str | None = Field(default=None, alias="transformName")
    record_type: str | None = Field(default=None, alias="recordType")
    parameters: dict[str, Any] | None = None
    operator: str | None = None
    primary_input_step_id: str | None = Field(default=None, alias="primaryInputStepId")
    secondary_input_step_id: str | None = Field(
        default=None, alias="secondaryInputStepId"
    )
    result_count: int | None = Field(default=None, alias="resultCount")
    wdk_step_id: int | None = Field(default=None, alias="wdkStepId")
    filters: list["StepFilterResponse"] | None = None
    analyses: list["StepAnalysisResponse"] | None = None
    reports: list["StepReportResponse"] | None = None

    model_config = {"populate_by_name": True}


class StepFilterResponse(BaseModel):
    """Filter attached to a step."""

    name: str
    value: Any
    disabled: bool = False


class StepAnalysisResponse(BaseModel):
    """Analysis configuration attached to a step."""

    analysis_type: str = Field(alias="analysisType")
    parameters: dict[str, Any] = Field(default_factory=dict)
    custom_name: str | None = Field(default=None, alias="customName")

    model_config = {"populate_by_name": True}


class StepReportResponse(BaseModel):
    """Report configuration attached to a step."""

    report_name: str = Field(default="standard", alias="reportName")
    config: dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


class StepFilterRequest(BaseModel):
    """Request to set or update a step filter."""

    value: Any
    disabled: bool = False


class StepAnalysisRequest(BaseModel):
    """Request to run a step analysis."""

    analysis_type: str = Field(alias="analysisType")
    parameters: dict[str, Any] = Field(default_factory=dict)
    custom_name: str | None = Field(default=None, alias="customName")

    model_config = {"populate_by_name": True}


class StepReportRequest(BaseModel):
    """Request to run a step report."""

    report_name: str = Field(default="standard", alias="reportName")
    config: dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


class StepCountsRequest(BaseModel):
    """Request to compute step counts from a plan."""

    site_id: str = Field(alias="siteId")
    plan: dict[str, Any]

    model_config = {"populate_by_name": True}


class StepCountsResponse(BaseModel):
    """Step counts keyed by local step ID."""

    counts: dict[str, int | None]


class StrategySummaryResponse(BaseModel):
    """Strategy summary for list views."""

    id: UUID
    name: str
    title: str | None = None
    site_id: str = Field(alias="siteId")
    record_type: str | None = Field(alias="recordType")
    step_count: int = Field(alias="stepCount")
    result_count: int | None = Field(default=None, alias="resultCount")
    wdk_strategy_id: int | None = Field(default=None, alias="wdkStrategyId")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")

    model_config = {"populate_by_name": True}


class OpenStrategyRequest(BaseModel):
    """Request to open a strategy."""

    strategy_id: UUID | None = Field(default=None, alias="strategyId")
    wdk_strategy_id: int | None = Field(default=None, alias="wdkStrategyId")
    site_id: str | None = Field(default=None, alias="siteId")

    model_config = {"populate_by_name": True}


class OpenStrategyResponse(BaseModel):
    """Open strategy response."""

    strategy_id: UUID = Field(alias="strategyId")

    model_config = {"populate_by_name": True}


class StrategyResponse(BaseModel):
    """Full strategy with steps."""

    id: UUID
    name: str
    title: str | None = None
    description: str | None = None
    site_id: str = Field(alias="siteId")
    record_type: str | None = Field(alias="recordType")
    steps: list[StepResponse]
    root_step_id: str | None = Field(alias="rootStepId")
    wdk_strategy_id: int | None = Field(default=None, alias="wdkStrategyId")
    messages: list[MessageResponse] | None = None
    thinking: ThinkingResponse | None = None
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")

    model_config = {"populate_by_name": True}


class CreateStrategyRequest(BaseModel):
    """Request to create a strategy."""

    name: str = Field(min_length=1, max_length=255)
    site_id: str = Field(alias="siteId")
    plan: dict[str, Any]

    model_config = {"populate_by_name": True}


class UpdateStrategyRequest(BaseModel):
    """Request to update a strategy."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    plan: dict[str, Any] | None = None
    wdk_strategy_id: int | None = Field(default=None, alias="wdkStrategyId")

    model_config = {"populate_by_name": True}


class PushResultResponse(BaseModel):
    """Result of pushing strategy to WDK."""

    wdk_strategy_id: int = Field(alias="wdkStrategyId")
    wdk_url: str = Field(alias="wdkUrl")

    model_config = {"populate_by_name": True}


# ============================================================================
# Results
# ============================================================================


class PreviewRequest(BaseModel):
    """Request to preview results."""

    strategy_id: UUID = Field(alias="strategyId")
    step_id: str = Field(alias="stepId")
    limit: int = Field(default=100, ge=1, le=1000)

    model_config = {"populate_by_name": True}


class PreviewResponse(BaseModel):
    """Preview results response."""

    total_count: int = Field(alias="totalCount")
    records: list[dict[str, Any]]
    columns: list[str]

    model_config = {"populate_by_name": True}


class DownloadRequest(BaseModel):
    """Request to download results."""

    strategy_id: UUID = Field(alias="strategyId")
    step_id: str = Field(alias="stepId")
    format: str = "csv"
    attributes: list[str] | None = None

    model_config = {"populate_by_name": True}


class DownloadResponse(BaseModel):
    """Download response with URL."""

    download_url: str = Field(alias="downloadUrl")
    expires_at: datetime = Field(alias="expiresAt")

    model_config = {"populate_by_name": True}

