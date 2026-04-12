"""HTTP schemas for structured plan actions."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from pathfinder.domain.strategy.plan_actions import (
    PlanParameterEdit,
    PlanQuestionAnswer,
)


class PlanActionRequest(BaseModel):
    """Structured control-plane action for an interactive plan."""

    action: Literal["approve", "reject", "suggest_changes"]
    plan_id: str = Field(alias="planId")
    trace_id: str | None = Field(default=None, alias="traceId")
    message_group_id: str | None = Field(default=None, alias="messageGroupId")
    source: str | None = None
    param_edits: list[PlanParameterEdit] = Field(
        default_factory=list,
        alias="paramEdits",
    )
    answers: list[PlanQuestionAnswer] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class PlanActionOperationResponse(BaseModel):
    """Operation envelope returned when a plan action starts streaming."""

    operation_id: str = Field(alias="operationId")
    strategy_id: UUID = Field(alias="strategyId")

    model_config = {"populate_by_name": True}
