"""Step request/response DTOs."""

from pydantic import BaseModel, Field

from veupath_chatbot.domain.strategy.ast import StepAnalysis, StepFilter, StepReport
from veupath_chatbot.domain.strategy.ops import ColocationParams
from veupath_chatbot.integrations.veupathdb.wdk_models import WDKValidation
from veupath_chatbot.platform.pydantic_base import CamelModel
from veupath_chatbot.platform.types import JSONObject


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


class PrimaryKeyPart(BaseModel):
    """A single part of a composite WDK primary key."""

    name: str
    value: str


class RecordDetailRequest(BaseModel):
    """Request to fetch a single record by primary key."""

    primary_key: list[PrimaryKeyPart] = Field(alias="primaryKey", min_length=1)

    model_config = {"populate_by_name": True}
