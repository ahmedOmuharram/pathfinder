"""Plan session request/response DTOs."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from .chat import MessageResponse, ThinkingResponse


class PlanSessionSummaryResponse(BaseModel):
    id: UUID
    site_id: str = Field(alias="siteId")
    title: str
    updated_at: datetime = Field(alias="updatedAt")
    created_at: datetime = Field(alias="createdAt")

    model_config = {"populate_by_name": True}


class PlanSessionResponse(BaseModel):
    id: UUID
    site_id: str = Field(alias="siteId")
    title: str
    messages: list[MessageResponse] | None = None
    thinking: ThinkingResponse | None = None
    planning_artifacts: list[dict[str, Any]] | None = Field(
        default=None, alias="planningArtifacts"
    )
    updated_at: datetime = Field(alias="updatedAt")
    created_at: datetime = Field(alias="createdAt")

    model_config = {"populate_by_name": True}


class OpenPlanSessionRequest(BaseModel):
    plan_session_id: UUID | None = Field(default=None, alias="planSessionId")
    site_id: str = Field(alias="siteId")
    title: str | None = None

    model_config = {"populate_by_name": True}


class OpenPlanSessionResponse(BaseModel):
    plan_session_id: UUID = Field(alias="planSessionId")

    model_config = {"populate_by_name": True}


class UpdatePlanSessionRequest(BaseModel):
    title: str | None = None


