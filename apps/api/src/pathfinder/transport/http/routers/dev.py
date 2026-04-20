"""Test-only endpoints (available only when chat_provider=mock)."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from pathfinder.platform.config import get_settings
from pathfinder.platform.errors import ForbiddenError
from pathfinder.platform.security import create_user_token
from pathfinder.transport.http.deps import UserRepo

router = APIRouter(prefix="/api/v1/dev", tags=["dev"])


def _is_mock_provider() -> bool:
    return get_settings().pathfinder_chat_provider.strip().lower() == "mock"


@router.post("/login")
async def dev_login(user_repo: UserRepo, user_id: str | None = None) -> JSONResponse:
    """Create a test user and return a valid auth token.

    Only available when ``PATHFINDER_CHAT_PROVIDER=mock`` in the test profile.

    Pass ``?user_id=worker-0`` to create isolated users per Playwright
    worker so parallel tests don't share data.
    """
    if not _is_mock_provider():
        raise ForbiddenError(title="Only available in mock mode")

    external_id = f"e2e-{user_id}@test.local" if user_id else "e2e@test.local"
    user = await user_repo.get_or_create_by_external_id(external_id)
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
