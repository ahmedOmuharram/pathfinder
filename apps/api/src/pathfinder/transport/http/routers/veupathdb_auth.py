"""VEuPathDB login bridge. Links a VEuPathDB session to an internal user token."""

from typing import TypedDict
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from pydantic import ConfigDict, Field, JsonValue
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.platform.config import get_settings
from pathfinder.platform.context import veupathdb_auth_token_ctx
from pathfinder.platform.errors import UnauthorizedError, ValidationError
from pathfinder.platform.logging import get_logger
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.platform.security import (
    create_user_token,
    get_optional_user,
    limiter,
)
from pathfinder.services.users import get_or_create_user_id
from pathfinder.services.wdk import get_site, get_wdk_client, password_login
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


class _WDKUserProperties(CamelModel):
    """Properties nested in a WDK current-user response."""

    model_config = ConfigDict(extra="ignore")
    first_name: str | None = Field(default=None)
    last_name: str | None = Field(default=None)


class _WDKUserResponse(CamelModel):
    """Typed parse of a WDK current-user response."""

    model_config = ConfigDict(extra="ignore")
    is_guest: bool = Field(default=True)
    email: str | None = None
    properties: _WDKUserProperties = Field(default_factory=_WDKUserProperties)


def _parse_wdk_user(raw: JsonValue) -> _WDKUserResponse | None:
    """Parse a raw WDK user response. Return None if the response is not an object."""
    if not isinstance(raw, dict):
        return None
    return _WDKUserResponse.model_validate(raw)


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


async def _resolve_veupathdb_email(
    veupathdb_token: str, site_id: str = "veupathdb"
) -> str | None:
    """Return the email of the current VEuPathDB user, or None for a guest."""
    reset_token = veupathdb_auth_token_ctx.set(veupathdb_token)
    try:
        site = get_site(site_id)
        client = get_wdk_client(site.id)
        raw = await client.get("/users/current")
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        logger.debug("Failed to resolve VEuPathDB email from token", error=str(exc))
        return None
    finally:
        veupathdb_auth_token_ctx.reset(reset_token)

    user = _parse_wdk_user(raw)
    if user is None:
        return None
    return user.email if not user.is_guest else None


async def _link_internal_user(
    session: AsyncSession, veupathdb_token: str, site_id: str = "veupathdb"
) -> tuple[str | None, str | None]:
    """Resolve the VEuPathDB identity and find or create the internal user.

    :returns: Tuple of (auth_token, email), or (None, None) if the session is invalid.
    """
    email = await _resolve_veupathdb_email(veupathdb_token, site_id)
    if not email:
        return None, None
    internal_id = await get_or_create_user_id(session, email)
    auth_token = create_user_token(internal_id)
    return auth_token, email


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

    auth_token, _email = await _link_internal_user(session, token, site_id)
    if not auth_token:
        raise UnauthorizedError(detail="Invalid email or password")
    return _build_success_response(token, auth_token)


@router.post("/logout", response_model=AuthSuccessResponse)
async def logout(
    site_id: str = Query("veupathdb", alias="siteId"),
) -> JSONResponse:
    """Clear the local auth cookies and log out of VEuPathDB."""
    auth_site = get_site(site_id)
    async with httpx.AsyncClient(
        base_url=auth_site.service_url, follow_redirects=True
    ) as client:
        try:
            await client.get("/logout")
        except httpx.HTTPError:
            logger.warning("Failed to log out of VEuPathDB")
    response = JSONResponse({"success": True})
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
    veupathdb_token = (
        request.headers.get("X-VEUPATHDB-AUTH")
        or request.headers.get("X-VEUPATHDB-AUTHORIZATION")
        or request.cookies.get("Authorization")
    )
    if not veupathdb_token:
        raise UnauthorizedError(detail="No VEuPathDB session")

    auth_token, _email = await _link_internal_user(session, veupathdb_token, site_id)
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
        mock_user_id = await get_optional_user(request, cookie_token)
        if mock_user_id is not None:
            return {
                "signedIn": True,
                "name": "E2E Test User",
                "email": "e2e@test.local",
            }

    user = await _fetch_wdk_user(site_id)
    if user is None:
        return {"signedIn": False, "name": None, "email": None}

    return _format_auth_status(user)


async def _fetch_wdk_user(site_id: str) -> _WDKUserResponse | None:
    """Fetch the current user from WDK. Return None on failure."""
    site = get_site(site_id)
    client = get_wdk_client(site.id)
    try:
        raw = await client.get("/users/current")
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        logger.debug("Failed to fetch VEuPathDB auth status", error=str(exc))
        return None
    return _parse_wdk_user(raw)


def _format_auth_status(user: _WDKUserResponse) -> _AuthStatusDict:
    """Format a parsed WDK user as an auth status."""
    props = user.properties
    name: str | None = None
    if props.first_name or props.last_name:
        name = " ".join(part for part in (props.first_name, props.last_name) if part)
    name = name or user.email
    return {"signedIn": not user.is_guest, "name": name, "email": user.email}
