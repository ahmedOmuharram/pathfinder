from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from assistant_core.platform.pydantic_base import CamelModel


class QuotaResponse(CamelModel):
    used_usd: Decimal
    limit_usd: Decimal
    total_tokens: int
    percent: float
    resets_at: datetime
