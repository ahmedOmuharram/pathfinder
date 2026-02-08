"""Strategy request/response DTOs."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from .chat import MessageResponse, ThinkingResponse
from .plan import StrategyPlan
from .steps import StepResponse


class StepCountsRequest(BaseModel):
    """Request to compute step counts from a plan."""

    site_id: str = Field(alias="siteId")
    plan: StrategyPlan

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


class WdkStrategySummaryResponse(BaseModel):
    """WDK strategy summary for list views."""

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
    plan: StrategyPlan

    model_config = {"populate_by_name": True}


class UpdateStrategyRequest(BaseModel):
    """Request to update a strategy."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    plan: StrategyPlan | None = None
    wdk_strategy_id: int | None = Field(default=None, alias="wdkStrategyId")

    model_config = {"populate_by_name": True}


class PushResultResponse(BaseModel):
    """Result of pushing strategy to WDK."""

    wdk_strategy_id: int = Field(alias="wdkStrategyId")
    wdk_url: str = Field(alias="wdkUrl")

    model_config = {"populate_by_name": True}
