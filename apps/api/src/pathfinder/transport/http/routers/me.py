from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from pathfinder.services import quota as quota_service
from pathfinder.services import user_preferences as prefs_service
from pathfinder.transport.http.deps import CurrentUser, DBSession
from pathfinder.transport.http.schemas.me import (
    QuotaResponse,
    UserPreferencesPatch,
    UserPreferencesResponse,
)

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


@router.get("/preferences", response_model=UserPreferencesResponse)
async def get_my_preferences(
    session: DBSession, user_id: CurrentUser,
) -> UserPreferencesResponse:
    prefs = await prefs_service.get_preferences(session, user_id)
    return UserPreferencesResponse(supervisor_model_id=prefs.supervisor_model_id)


@router.patch("/preferences", response_model=UserPreferencesResponse)
async def update_my_preferences(
    body: UserPreferencesPatch, session: DBSession, user_id: CurrentUser,
) -> UserPreferencesResponse:
    patch = body.model_dump(exclude_unset=True, by_alias=False)
    try:
        prefs = await prefs_service.apply_patch(session, user_id, patch)
    except prefs_service.UnknownModelError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc),
        ) from exc
    return UserPreferencesResponse(supervisor_model_id=prefs.supervisor_model_id)
