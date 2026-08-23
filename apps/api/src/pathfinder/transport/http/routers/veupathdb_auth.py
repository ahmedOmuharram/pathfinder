"""VEuPathDB login bridge. Links a VEuPathDB session to an internal user token."""

from typing import TypedDict
from urllib.parse import urlparse

from assistant_core.platform.logging import get_logger
from assistant_core.platform.pydantic_base import CamelModel
from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.platform.config import get_settings
from pathfinder.platform.errors import UnauthorizedError, ValidationError
from pathfinder.platform.security import (
    create_user_token,
    decode_user_id,
    limiter,
)
from pathfinder.services.users import get_or_create_user_id
from pathfinder.services.wdk import password_login, password_logout
from pathfinder.services.wdk_identity import (
    WDKCurrentUser,
    fetch_wdk_user,
    resolve_veupathdb_email,
)
from pathfinder.transport.http.deps import DBSession
from pathfinder.transport.http.schemas import (
    AuthStatusResponse,
    AuthSuccessResponse,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/veupathdb/auth", tags=["veupathdb-auth"])


class LoginPayload(CamelModel):
    email: str
    password: str


def _pick_redirect_url(candidate: str | None) -> str:
    settings = get_settings()
    allowed = settings.cors_origins or []
    if candidate:
        try:
            parsed = urlparse(candidate)
            candidate_origin = f"{parsed.scheme}://{parsed.netloc}"
            if candidate_origin in allowed:
                return candidate
        except (ValueError, TypeError) as exc:
            logger.debug(
                "Failed to parse redirect URL candidate",
                candidate=candidate,
                error=str(exc),
            )
    return allowed[0] if allowed else "http://localhost:3000"


async def _link_internal_user(
    session: AsyncSession, veupathdb_token: str, site_id: str
) -> str | None:
    """Mint the internal auth token for the VEuPathDB identity, or None."""
    email = await resolve_veupathdb_email(veupathdb_token, site_id)
    if not email:
        return None
    internal_id = await get_or_create_user_id(session, email)
    return create_user_token(internal_id)


def _build_success_response(
    veupathdb_token: str,
    auth_token: str | None,
) -> JSONResponse:
    """Build a response that sets both auth cookies.

    Tokens travel only in httpOnly cookies. The response body must not carry them.
    """
    body = {"success": True}

    settings = get_settings()
    secure_cookie = settings.api_env != "development"

    resp = JSONResponse(body)
    resp.set_cookie(
        key="Authorization",
        value=veupathdb_token,
        httponly=True,
        samesite="lax",
        secure=secure_cookie,
        path="/",
    )
    if auth_token:
        resp.set_cookie(
            key="pathfinder-auth",
            value=auth_token,
            httponly=True,
            samesite="lax",
            secure=secure_cookie,
            path="/",
        )
    return resp


@router.post("/login", response_model=AuthSuccessResponse)
@limiter.limit("10/minute")
async def login_with_password(
    request: Request,
    session: DBSession,
    payload: LoginPayload | None = None,
    redirect_to: str | None = Query(None, alias="redirectTo"),
    site_id: str = Query("veupathdb", alias="siteId"),
) -> JSONResponse:
    """Log in to VEuPathDB, link the internal user, and set the auth cookies."""
    if not payload:
        raise ValidationError(
            detail="Email and password required",
            errors=[
                {"path": "email", "message": "Required", "code": "MISSING_FIELD"},
                {"path": "password", "message": "Required", "code": "MISSING_FIELD"},
            ],
        )

    email = payload.email
    password = payload.password
    if not email or not password:
        raise ValidationError(
            detail="Email and password required",
            errors=[
                {"path": "email", "message": "Required", "code": "MISSING_FIELD"},
                {"path": "password", "message": "Required", "code": "MISSING_FIELD"},
            ],
        )

    token = await password_login(
        site_id, email, password, redirect_url=_pick_redirect_url(redirect_to)
    )

    if not token:
        logger.warning(
            "No non-guest Authorization cookie in VEuPathDB login response "
            "(credentials likely invalid)",
        )
        raise UnauthorizedError(detail="Invalid email or password")

    auth_token = await _link_internal_user(session, token, site_id)
    if not auth_token:
        raise UnauthorizedError(detail="Invalid email or password")
    return _build_success_response(token, auth_token)


async def logout_of_veupathdb(veupathdb_token: str | None, site_id: str) -> bool:
    """Ask WDK to end the session the token belongs to.

    WDK logs out whoever made the request, and answers an uncredentialed one as
    a guest, so a logout without the token ends nobody's session.
    """
    if not veupathdb_token:
        return False
    ended: bool = await password_logout(site_id, veupathdb_token)
    if not ended:
        logger.warning("VEuPathDB did not end the session", site_id=site_id)
    return ended


@router.post("/logout", response_model=AuthSuccessResponse)
async def logout(
    request: Request,
    site_id: str = Query("veupathdb", alias="siteId"),
) -> JSONResponse:
    """Clear the local auth cookies and end the VEuPathDB session.

    The cookies are cleared either way: the local session is over even when WDK
    could not be reached. ``success`` reports what WDK did.
    """
    veupathdb_token = request.headers.get("X-VEUPATHDB-AUTH") or request.cookies.get(
        "Authorization"
    )
    ended = await logout_of_veupathdb(veupathdb_token, site_id)
    response = JSONResponse({"success": ended})
    response.delete_cookie(key="Authorization", path="/")
    response.delete_cookie(key="pathfinder-auth", path="/")
    return response


@router.post("/refresh", response_model=AuthSuccessResponse)
async def refresh_internal_auth(
    request: Request,
    session: DBSession,
    site_id: str = Query("veupathdb", alias="siteId"),
) -> JSONResponse:
    """Re-derive the internal auth token from a live VEuPathDB session.

    Use this when the internal token is absent or expired but the VEuPathDB
    cookie is still valid.
    """
    existing = request.cookies.get("pathfinder-auth")
    if existing and decode_user_id(existing) is not None:
        return JSONResponse({"success": True})

    veupathdb_token = (
        request.headers.get("X-VEUPATHDB-AUTH")
        or request.headers.get("X-VEUPATHDB-AUTHORIZATION")
        or request.cookies.get("Authorization")
    )
    if not veupathdb_token:
        raise UnauthorizedError(detail="No VEuPathDB session")

    auth_token = await _link_internal_user(session, veupathdb_token, site_id)
    if not auth_token:
        raise UnauthorizedError(detail="VEuPathDB session expired or invalid")

    settings = get_settings()
    secure_cookie = settings.api_env != "development"

    resp = JSONResponse({"success": True})
    resp.set_cookie(
        key="pathfinder-auth",
        value=auth_token,
        httponly=True,
        samesite="lax",
        secure=secure_cookie,
        path="/",
    )
    return resp


class _AuthStatusDict(TypedDict):
    signedIn: bool
    name: str | None
    email: str | None


@router.get("/status", response_model=AuthStatusResponse)
async def auth_status(
    request: Request,
    site_id: str = Query("veupathdb", alias="siteId"),
) -> _AuthStatusDict:
    """Return the current VEuPathDB auth status.

    A mock chat provider has no VEuPathDB session, so the internal cookie
    alone proves identity there.
    """
    settings = get_settings()
    if settings.pathfinder_chat_provider.strip().lower() == "mock":
        cookie_token = request.cookies.get("pathfinder-auth")
        if cookie_token and decode_user_id(cookie_token) is not None:
            return {
                "signedIn": True,
                "name": "E2E Test User",
                "email": "e2e@test.local",
            }

    user = await fetch_wdk_user(site_id)
    if user is None:
        return {"signedIn": False, "name": None, "email": None}

    return _format_auth_status(user)


def _format_auth_status(user: WDKCurrentUser) -> _AuthStatusDict:
    """Format a parsed WDK user as an auth status."""
    props = user.properties
    name: str | None = None
    if props.first_name or props.last_name:
        name = " ".join(part for part in (props.first_name, props.last_name) if part)
    name = name or user.email
    return {"signedIn": not user.is_guest, "name": name, "email": user.email}
