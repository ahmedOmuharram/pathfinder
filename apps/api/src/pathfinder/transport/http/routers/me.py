from __future__ import annotations

from fastapi import APIRouter

from pathfinder.services import quota as quota_service
from pathfinder.transport.http.deps import CurrentUser, DBSession
from pathfinder.transport.http.schemas.me import QuotaResponse

router = APIRouter(prefix="/api/v1/me", tags=["me"])


@router.get("/quota", response_model=QuotaResponse)
async def get_my_quota(session: DBSession, user_id: CurrentUser) -> QuotaResponse:
    q = await quota_service.get_current(session, user_id)
    return QuotaResponse(
        used_usd=q.used_usd,
        limit_usd=q.limit_usd,
        total_tokens=q.total_tokens,
        percent=q.percent,
        resets_at=q.resets_at,
    )
