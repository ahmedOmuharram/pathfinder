"""Service-layer strategy DTOs shared across services, AI, and transport.

These types depend on both domain models and integration types (WDKValidation),
so they belong in the service layer — the only layer that can import from both
domain and integrations.
"""

from veupath_chatbot.domain.strategy.ast import (
    PlanStepNode,
    StepAnalysis,
    StepFilter,
    StepReport,
)
from veupath_chatbot.domain.strategy.ops import ColocationParams
from veupath_chatbot.integrations.veupathdb.wdk_models import WDKValidation
from veupath_chatbot.platform.pydantic_base import CamelModel
from veupath_chatbot.platform.types import JSONObject


class StrategyPlanPayload(CamelModel):
    """Wire format for strategy plans (API request/response).

    Wire format for strategy plans shared between API request/response and persistence.
    """

    record_type: str
    root: PlanStepNode
    name: str | None = None
    description: str | None = None
    metadata: JSONObject | None = None
    step_counts: dict[str, int] | None = None
    wdk_step_ids: dict[str, int] | None = None
    step_validations: dict[str, WDKValidation] | None = None


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
