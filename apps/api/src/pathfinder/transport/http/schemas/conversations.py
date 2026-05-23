"""Conversation request/response DTOs — unified chat + strategy shape."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from pathfinder.domain.strategy.strategy_ast import StrategyAst
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.services.strategies.schemas import (
    StepResponse,
)


class StepCountsRequest(CamelModel):
    site_id: str
    strategy_ast: StrategyAst


class StepCountsResponse(CamelModel):
    counts: dict[str, int | None]


class OpenConversationRequest(CamelModel):
    conversation_id: UUID | None = Field(default=None)
    wdk_strategy_id: int | None = Field(default=None)
    site_id: str | None = Field(default=None)


class OpenConversationResponse(CamelModel):
    conversation_id: UUID


class BeginConversationRequest(CamelModel):
    site_id: str = Field(min_length=1, max_length=64)
    experiment_id: str | None = None
    seed_text: str | None = Field(default=None, max_length=4000)


class BeginConversationResponse(CamelModel):
    conversation_id: UUID
    is_new: bool
    name: str


class ConversationSummaryResponse(CamelModel):
    id: UUID
    name: str
    site_id: str
    record_type: str | None
    wdk_strategy_id: int | None = Field(default=None)
    is_saved: bool = Field(default=False)
    step_count: int
    estimated_size: int | None = Field(default=None)
    gene_set_id: str | None = Field(default=None)
    experiment_id: str | None = Field(default=None)
    dismissed_at: datetime | None = Field(default=None)
    created_at: datetime
    updated_at: datetime
    parent_conversation_id: UUID | None = Field(default=None,)
    parent_message_id: UUID | None = Field(default=None,)


class ConversationResponse(CamelModel):
    id: UUID
    name: str
    title: str | None = None
    description: str | None = None
    site_id: str
    record_type: str | None
    steps: list[StepResponse] = Field(default_factory=list)
    root_step_id: str | None = Field(default=None)
    wdk_strategy_id: int | None = Field(default=None)
    is_saved: bool = Field(default=False)
    created_at: datetime
    updated_at: datetime
    step_count: int | None = Field(default=None)
    estimated_size: int | None = Field(default=None)
    wdk_url: str | None = Field(default=None)
    gene_set_id: str | None = Field(default=None)
    experiment_id: str | None = Field(default=None)
    dismissed_at: datetime | None = Field(default=None)
    total_tokens: int = Field(default=0)
    total_cost_usd: Decimal = Field(default_factory=lambda: Decimal(0))
    parent_conversation_id: UUID | None = Field(default=None,)
    parent_message_id: UUID | None = Field(default=None,)


class CreateConversationRequest(CamelModel):
    name: str = Field(min_length=1, max_length=255)
    site_id: str
    strategy_ast: StrategyAst


class UpdateConversationRequest(CamelModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    strategy_ast: StrategyAst | None = Field(default=None)
    wdk_strategy_id: int | None = Field(default=None)
    is_saved: bool | None = Field(default=None)


class PushConversationRequest(CamelModel):
    name: str = Field(min_length=1, max_length=255)
    site_id: str
    strategy_ast: StrategyAst
    description: str | None = Field(default=None, max_length=2000)


class ConversationPatchBody(CamelModel):
    """Sidebar patch payload — rename / toggle saved."""

    name: str | None = None
    is_saved: bool | None = Field(default=None)


class ConversationDuplicateResponse(CamelModel):
    id: UUID
    name: str


class SaveSubstrategyRequest(CamelModel):
    """POST body for saving a subtree of the active strategy."""

    step_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)


class SaveSubstrategyResponse(CamelModel):
    wdk_strategy_id: int
    name: str
    description: str | None = None
    record_type: str
    root_step_id: int


class ForkConversationRequest(CamelModel):
    from_message_id: UUID
