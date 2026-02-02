"""Results request/response DTOs."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class PreviewRequest(BaseModel):
    """Request to preview results."""

    strategy_id: UUID = Field(alias="strategyId")
    step_id: str = Field(alias="stepId")
    limit: int = Field(default=100, ge=1, le=1000)

    model_config = {"populate_by_name": True}


class PreviewResponse(BaseModel):
    """Preview results response."""

    total_count: int = Field(alias="totalCount")
    records: list[dict[str, Any]]
    columns: list[str]

    model_config = {"populate_by_name": True}


class DownloadRequest(BaseModel):
    """Request to download results."""

    strategy_id: UUID = Field(alias="strategyId")
    step_id: str = Field(alias="stepId")
    format: str = "csv"
    attributes: list[str] | None = None

    model_config = {"populate_by_name": True}


class DownloadResponse(BaseModel):
    """Download response with URL."""

    download_url: str = Field(alias="downloadUrl")
    expires_at: datetime = Field(alias="expiresAt")

    model_config = {"populate_by_name": True}
