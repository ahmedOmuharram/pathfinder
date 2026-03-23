"""Step request/response DTOs."""

from pydantic import BaseModel, Field

from veupath_chatbot.domain.strategy.ast import StepAnalysis, StepFilter, StepReport
from veupath_chatbot.domain.strategy.ops import ColocationParams
from veupath_chatbot.integrations.veupathdb.wdk_models import WDKValidation
from veupath_chatbot.platform.pydantic_base import CamelModel
from veupath_chatbot.platform.types import JSONObject, JSONValue


class StepFiltersResponse(BaseModel):
    """Container for step filters."""

    filters: list[StepFilter]


class StepAnalysisRunResponse(BaseModel):
    """Result of running a step analysis."""

    analysis: StepAnalysis
    wdk: JSONObject | None = None


class StepReportRunResponse(BaseModel):
    """Result of running a step report."""

    report: StepReport
    wdk: JSONObject | None = None


class StepResponse(CamelModel):
    """Strategy step — WDK-aligned fields."""

    id: str
    kind: str | None = None
    display_name: str | None = None
    search_name: str | None = None
    record_type: str | None = None
    parameters: JSONObject | None = None
    operator: str | None = None
    colocation_params: ColocationParams | None = None
    primary_input_step_id: str | None = None
    secondary_input_step_id: str | None = None
    estimated_size: int | None = None
    wdk_step_id: int | None = None
    is_built: bool = False
    is_filtered: bool = False
    validation: WDKValidation | None = None
    filters: list[StepFilter] | None = None
    analyses: list[StepAnalysis] | None = None
    reports: list[StepReport] | None = None


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


class PrimaryKeyPart(BaseModel):
    """A single part of a composite WDK primary key."""

    name: str
    value: str


class RecordDetailRequest(BaseModel):
    """Request to fetch a single record by primary key."""

    primary_key: list[PrimaryKeyPart] = Field(alias="primaryKey", min_length=1)

    model_config = {"populate_by_name": True}
