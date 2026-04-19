from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import Field

from pathfinder.platform.pydantic_base import CamelModel


class QuotaResponse(CamelModel):
    used_usd: Decimal
    limit_usd: Decimal
    total_tokens: int
    percent: float
    resets_at: datetime


class UserPreferencesResponse(CamelModel):
    supervisor_model_id: str | None = None


class UserPreferencesPatch(CamelModel):
    """Partial update — only present fields are applied."""

    supervisor_model_id: str | None = Field(default=None)
