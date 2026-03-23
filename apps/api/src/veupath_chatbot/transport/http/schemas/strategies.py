"""Strategy request/response DTOs."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from veupath_chatbot.domain.strategy.ast import StrategyAST

from .chat import MessageResponse, ThinkingResponse
from .steps import StepResponse


class StepCountsRequest(BaseModel):
    """Request to compute step counts from a plan."""

    site_id: str = Field(alias="siteId")
    plan: StrategyAST

    model_config = {"populate_by_name": True}


class StepCountsResponse(BaseModel):
    """Step counts keyed by local step ID."""

    counts: dict[str, int | None]


class WdkStrategySummaryResponse(BaseModel):
    """WDK strategy summary for list views (backend-only)."""

    wdk_strategy_id: int = Field(alias="wdkStrategyId")
    name: str
    site_id: str = Field(alias="siteId")
    wdk_url: str | None = Field(default=None, alias="wdkUrl")
    root_step_id: int | None = Field(default=None, alias="rootStepId")
    is_saved: bool | None = Field(default=None, alias="isSaved")
    is_internal: bool = Field(default=False, alias="isInternal")

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
    """Unified strategy response — used for both list and detail views.

    List views: ``steps`` is ``[]``, ``stepCount``/``estimatedSize`` are populated.
    Detail views: ``steps`` is populated, summary fields may also be set.
    """

    id: UUID
    name: str
    title: str | None = None
    description: str | None = None
    site_id: str = Field(alias="siteId")
    record_type: str | None = Field(alias="recordType")
    steps: list[StepResponse] = Field(default_factory=list)
    root_step_id: str | None = Field(default=None, alias="rootStepId")
    wdk_strategy_id: int | None = Field(default=None, alias="wdkStrategyId")
    is_saved: bool = Field(default=False, alias="isSaved")
    messages: list[MessageResponse] | None = None
    thinking: ThinkingResponse | None = None
    model_id: str | None = Field(default=None, alias="modelId")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    # Summary fields — always set, avoids needing steps loaded.
    step_count: int | None = Field(default=None, alias="stepCount")
    estimated_size: int | None = Field(default=None, alias="estimatedSize")
    wdk_url: str | None = Field(default=None, alias="wdkUrl")
    gene_set_id: str | None = Field(default=None, alias="geneSetId")
    dismissed_at: datetime | None = Field(default=None, alias="dismissedAt")

    model_config = {"populate_by_name": True}


class CreateStrategyRequest(BaseModel):
    """Request to create a strategy."""

    name: str = Field(min_length=1, max_length=255)
    site_id: str = Field(alias="siteId")
    plan: StrategyAST

    model_config = {"populate_by_name": True}


class UpdateStrategyRequest(BaseModel):
    """Request to update a strategy."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    plan: StrategyAST | None = None
    wdk_strategy_id: int | None = Field(default=None, alias="wdkStrategyId")
    is_saved: bool | None = Field(default=None, alias="isSaved")

    model_config = {"populate_by_name": True}
