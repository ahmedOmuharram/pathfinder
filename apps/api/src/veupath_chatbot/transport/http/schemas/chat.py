"""Chat request/response DTOs."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request to send a chat message."""

    strategy_id: UUID | None = Field(default=None, alias="strategyId")
    site_id: str = Field(alias="siteId")
    message: str = Field(min_length=1, max_length=10000)

    model_config = {"populate_by_name": True}


class ToolCallResponse(BaseModel):
    """Tool call information."""

    id: str
    name: str
    arguments: dict[str, Any]
    result: str | None = None


class SubKaniActivityResponse(BaseModel):
    """Sub-kani tool call activity."""

    calls: dict[str, list[ToolCallResponse]]
    status: dict[str, str]


class ThinkingResponse(BaseModel):
    """In-progress tool call state."""

    tool_calls: list[ToolCallResponse] | None = Field(default=None, alias="toolCalls")
    sub_kani_calls: dict[str, list[ToolCallResponse]] | None = Field(
        default=None, alias="subKaniCalls"
    )
    sub_kani_status: dict[str, str] | None = Field(
        default=None, alias="subKaniStatus"
    )
    updated_at: datetime | None = Field(default=None, alias="updatedAt")

    model_config = {"populate_by_name": True}


class MessageResponse(BaseModel):
    """Chat message."""

    role: str
    content: str
    tool_calls: list[ToolCallResponse] | None = Field(default=None, alias="toolCalls")
    sub_kani_activity: SubKaniActivityResponse | None = Field(
        default=None, alias="subKaniActivity"
    )
    timestamp: datetime

    model_config = {"populate_by_name": True}
