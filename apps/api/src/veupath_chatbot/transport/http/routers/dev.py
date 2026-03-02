"""Development-only endpoints (available only when chat_provider=mock)."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from veupath_chatbot.platform.config import get_settings
from veupath_chatbot.platform.errors import ForbiddenError
from veupath_chatbot.platform.security import create_user_token
from veupath_chatbot.transport.http.deps import UserRepo

router = APIRouter(prefix="/api/v1/dev", tags=["dev"])


def _is_mock_provider() -> bool:
    return get_settings().chat_provider.strip().lower() == "mock"


@router.post("/login")
async def dev_login(user_repo: UserRepo) -> JSONResponse:
    """Create a test user and return a valid auth token.

    Only available when ``PATHFINDER_CHAT_PROVIDER=mock`` (e2e / local dev).
    """
    if not _is_mock_provider():
        raise ForbiddenError(title="Only available in mock mode")

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
