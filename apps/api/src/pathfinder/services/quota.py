"""Per-user monthly USD quota service.

One budget per user, denominated in USD, rolling over on the first of each
month (UTC). Cost is recorded per application and the cap counts every
application of the user. Agents accumulate cost on turn completion; the chat
route does a pre-flight ``check_allowed`` gate and returns 429 when a user is
at 100%. Warnings fire at 80% (soft) on the frontend via the
:class:`QuotaStatus` ``percent`` field.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.persistence.models import MonthlyUsage, User
from pathfinder.platform.config import get_settings
from pathfinder.platform.context import calling_application
from pathfinder.platform.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class QuotaStatus:
    """Snapshot of a user's current monthly quota."""

    used_usd: Decimal
    limit_usd: Decimal
    total_tokens: int
    percent: float
    resets_at: datetime


def current_period_start(now: datetime | None = None) -> date:
    """First-of-month UTC date for the current period."""
    ref = now.astimezone(UTC) if now else datetime.now(UTC)
    return date(ref.year, ref.month, 1)


_MONTHS_PER_YEAR = 12


def next_period_start(now: datetime | None = None) -> datetime:
    """First-of-next-month at 00:00 UTC."""
    ref = now.astimezone(UTC) if now else datetime.now(UTC)
    if ref.month == _MONTHS_PER_YEAR:
        return datetime(ref.year + 1, 1, 1, tzinfo=UTC)
    return datetime(ref.year, ref.month + 1, 1, tzinfo=UTC)


async def _effective_limit_usd(session: AsyncSession, user_id: UUID) -> Decimal:
    settings = get_settings()
    default = Decimal(str(settings.pathfinder_user_monthly_cost_limit_usd))
    override = await session.scalar(
        select(User.monthly_cost_limit_usd).where(User.id == user_id)
    )
    if override is None:
        return default
    return Decimal(str(override))


async def get_current(session: AsyncSession, user_id: UUID) -> QuotaStatus:
    """Return the user's usage for the current monthly period.

    The budget belongs to the user, so every application the user drove in the
    period counts against the same limit.
    """
    period = current_period_start()
    totals = (
        await session.execute(
            select(
                func.coalesce(func.sum(MonthlyUsage.total_cost_usd), 0),
                func.coalesce(func.sum(MonthlyUsage.total_tokens), 0),
            ).where(
                MonthlyUsage.user_id == user_id,
                MonthlyUsage.period_start == period,
            ),
        )
    ).one()
    used = Decimal(totals[0])
    tokens = int(totals[1])
    limit = await _effective_limit_usd(session, user_id)
    percent = float(used / limit) if limit > 0 else 0.0
    return QuotaStatus(
        used_usd=used,
        limit_usd=limit,
        total_tokens=tokens,
        percent=percent,
        resets_at=next_period_start(),
    )


async def check_allowed(session: AsyncSession, user_id: UUID) -> QuotaStatus:
    """Return the quota status; caller enforces the hard block at 100%."""
    return await get_current(session, user_id)


async def accumulate(
    session: AsyncSession,
    *,
    user_id: UUID,
    tokens: int,
    cost_usd: Decimal,
) -> None:
    """Upsert the current-period row of the calling application with the delta."""
    if tokens <= 0 and cost_usd <= 0:
        return

    period = current_period_start()
    stmt = (
        pg_insert(MonthlyUsage)
        .values(
            user_id=user_id,
            application_id=calling_application(),
            period_start=period,
            total_cost_usd=cost_usd,
            total_tokens=tokens,
        )
        .on_conflict_do_update(
            index_elements=["user_id", "application_id", "period_start"],
            set_={
                "total_cost_usd": MonthlyUsage.total_cost_usd + cost_usd,
                "total_tokens": MonthlyUsage.total_tokens + tokens,
                "updated_at": datetime.now(UTC),
            },
        )
    )
    await session.execute(stmt)
