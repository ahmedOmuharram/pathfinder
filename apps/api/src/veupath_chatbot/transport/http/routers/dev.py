"""Development-only endpoints (available only when PATHFINDER_CHAT_PROVIDER=mock)."""

from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from veupath_chatbot.platform.security import create_user_token
from veupath_chatbot.transport.http.deps import UserRepo

router = APIRouter(prefix="/api/v1/dev", tags=["dev"])


def _is_mock_provider() -> bool:
    return (os.environ.get("PATHFINDER_CHAT_PROVIDER") or "").strip().lower() == "mock"


@router.post("/login")
async def dev_login(user_repo: UserRepo) -> JSONResponse:
    """Create a test user and return a valid auth token.

    Only available when ``PATHFINDER_CHAT_PROVIDER=mock`` (e2e / local dev).
    """
    if not _is_mock_provider():
        raise HTTPException(status_code=403, detail="Only available in mock mode")

    user = await user_repo.get_or_create_by_external_id("e2e@test.local")
    auth_token = create_user_token(user.id)

    resp = JSONResponse({"authToken": auth_token, "userId": str(user.id)})
    resp.set_cookie(
        key="pathfinder-auth",
        value=auth_token,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return resp
