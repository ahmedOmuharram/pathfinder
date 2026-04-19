"""Conversation request/response DTOs — unified chat + strategy shape."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from pathfinder.domain.strategy.strategy_ast import StrategyAst
from pathfinder.platform.types import JSONObject
from pathfinder.services.strategies.schemas import (
    StepResponse,
)


class StepCountsRequest(BaseModel):
    site_id: str = Field(alias="siteId")
    strategy_ast: StrategyAst = Field(alias="strategyAst")

    model_config = {"populate_by_name": True}


class StepCountsResponse(BaseModel):
    counts: dict[str, int | None]


class OpenConversationRequest(BaseModel):
    conversation_id: UUID | None = Field(default=None, alias="conversationId")
    wdk_strategy_id: int | None = Field(default=None, alias="wdkStrategyId")
    site_id: str | None = Field(default=None, alias="siteId")

    model_config = {"populate_by_name": True}


class OpenConversationResponse(BaseModel):
    conversation_id: UUID = Field(alias="conversationId")

    model_config = {"populate_by_name": True}


class ConversationSummaryResponse(BaseModel):
    id: UUID
    name: str
    site_id: str = Field(alias="siteId")
    record_type: str | None = Field(alias="recordType")
    wdk_strategy_id: int | None = Field(default=None, alias="wdkStrategyId")
    is_saved: bool = Field(default=False, alias="isSaved")
    step_count: int = Field(alias="stepCount")
    estimated_size: int | None = Field(default=None, alias="estimatedSize")
    gene_set_id: str | None = Field(default=None, alias="geneSetId")
    experiment_id: str | None = Field(default=None, alias="experimentId")
    dismissed_at: datetime | None = Field(default=None, alias="dismissedAt")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    parent_conversation_id: UUID | None = Field(
        default=None, alias="parentConversationId",
    )
    parent_message_id: UUID | None = Field(
        default=None, alias="parentMessageId",
    )

    model_config = {"populate_by_name": True}


class ConversationResponse(BaseModel):
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
    pipeline: JSONObject | None = None
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    step_count: int | None = Field(default=None, alias="stepCount")
    estimated_size: int | None = Field(default=None, alias="estimatedSize")
    wdk_url: str | None = Field(default=None, alias="wdkUrl")
    gene_set_id: str | None = Field(default=None, alias="geneSetId")
    experiment_id: str | None = Field(default=None, alias="experimentId")
    dismissed_at: datetime | None = Field(default=None, alias="dismissedAt")
    total_tokens: int = Field(default=0, alias="totalTokens")
    total_cost_usd: Decimal = Field(
        default_factory=lambda: Decimal(0), alias="totalCostUsd",
    )
    supervisor_model_id: str | None = Field(
        default=None, alias="supervisorModelId",
    )
    parent_conversation_id: UUID | None = Field(
        default=None, alias="parentConversationId",
    )
    parent_message_id: UUID | None = Field(
        default=None, alias="parentMessageId",
    )

    model_config = {"populate_by_name": True}


class CreateConversationRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    site_id: str = Field(alias="siteId")
    strategy_ast: StrategyAst = Field(alias="strategyAst")

    model_config = {"populate_by_name": True}


class UpdateConversationRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    strategy_ast: StrategyAst | None = Field(default=None, alias="strategyAst")
    wdk_strategy_id: int | None = Field(default=None, alias="wdkStrategyId")
    is_saved: bool | None = Field(default=None, alias="isSaved")
    supervisor_model_id: str | None = Field(default=None, alias="supervisorModelId")

    model_config = {"populate_by_name": True}


class PushConversationRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    site_id: str = Field(alias="siteId")
    strategy_ast: StrategyAst = Field(alias="strategyAst")
    description: str | None = Field(default=None, max_length=2000)

    model_config = {"populate_by_name": True}


class ConversationPatchBody(BaseModel):
    """Sidebar patch payload — rename / toggle saved."""

    name: str | None = None
    is_saved: bool | None = Field(default=None, alias="isSaved")

    model_config = {"populate_by_name": True}


class ConversationDuplicateResponse(BaseModel):
    id: UUID
    name: str

    model_config = {"populate_by_name": True}


class ForkConversationRequest(BaseModel):
    from_message_id: UUID = Field(alias="fromMessageId")

    model_config = {"populate_by_name": True}
