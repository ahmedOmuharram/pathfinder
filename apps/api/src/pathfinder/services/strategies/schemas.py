"""Service-layer strategy DTOs shared across services, AI, and transport."""

from pathfinder.domain.strategy.ast import (
    StepAnalysis,
    StepFilter,
    StepReport,
)
from pathfinder.domain.strategy.ops import ColocationParams
from pathfinder.domain.strategy.types import DecodedParams
from pathfinder.domain.strategy.validation import StepValidation
from pathfinder.platform.pydantic_base import CamelModel


class StepResponse(CamelModel):
    """Strategy step — WDK-aligned fields."""

    id: str
    kind: str | None = None
    display_name: str | None = None
    search_name: str | None = None
    record_type: str | None = None
    parameters: DecodedParams | None = None
    operator: str | None = None
    colocation_params: ColocationParams | None = None
    primary_input_step_id: str | None = None
    secondary_input_step_id: str | None = None
    estimated_size: int | None = None
    wdk_step_id: int | None = None
    is_built: bool = False
    is_filtered: bool = False
    wdk_push_error: str | None = None
    validation: StepValidation | None = None
    filters: list[StepFilter] | None = None
    analyses: list[StepAnalysis] | None = None
    reports: list[StepReport] | None = None
