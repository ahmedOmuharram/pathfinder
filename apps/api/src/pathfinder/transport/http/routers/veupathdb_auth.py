"""VEuPathDB OAuth login bridge.

On successful VEuPathDB login the endpoint also creates/looks-up the internal
Pathfinder user (via ``User.external_id = email``) and returns a
``pathfinder-auth`` token so the frontend has a stable identity across sessions.
"""

import base64
import binascii
import json
from typing import TypedDict
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from pydantic import ConfigDict, Field, JsonValue

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
from pathfinder.services.wdk import get_site, get_wdk_client
from pathfinder.transport.http.deps import UserRepo
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
    """Properties nested inside a WDK ``/users/current`` response."""

    model_config = ConfigDict(extra="ignore")
    first_name: str | None = Field(default=None)
    last_name: str | None = Field(default=None)

class _WDKUserResponse(CamelModel):
    """Typed parse of WDK ``/users/current`` — replaces isinstance chains."""

    model_config = ConfigDict(extra="ignore")
    is_guest: bool = Field(default=True)
    email: str | None = None
    properties: _WDKUserProperties = Field(default_factory=_WDKUserProperties)

def _parse_wdk_user(raw: JsonValue) -> _WDKUserResponse | None:
    """Parse a raw WDK user response into a typed model.

    Returns ``None`` when the response is not a dict (e.g. error string).
    """
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

_JWT_MIN_SEGMENTS = 2


def _is_guest_jwt(token: str) -> bool:
    parts = token.split(".")
    if len(parts) < _JWT_MIN_SEGMENTS:
        return True
    payload_b64 = parts[1]
    padded = payload_b64 + "=" * (-len(payload_b64) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded).decode("utf-8")
        payload = json.loads(raw)
    except (ValueError, binascii.Error):
        return True
    return bool(payload.get("is_guest", False))

def _extract_auth_cookie(set_cookie_headers: list[str]) -> str | None:
    candidates: list[str] = []
    for header in set_cookie_headers:
        if not header.startswith("Authorization="):
            continue
        value = header.split(";", 1)[0].split("=", 1)[1].strip('"')
        if value:
            candidates.append(value)
    for token in candidates:
        if not _is_guest_jwt(token):
            return token
    return None

async def _resolve_veupathdb_email(
    veupathdb_token: str, site_id: str = "veupathdb"
) -> str | None:
    """Call VEuPathDB ``/users/current`` and return the user's email (or None)."""
    # Temporarily set the context var so the WDK client picks up the token.
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
    user_repo: UserRepo, veupathdb_token: str, site_id: str = "veupathdb"
) -> tuple[str | None, str | None]:
    """Resolve VEuPathDB identity and create/lookup the internal user.

    Returns ``(auth_token, email)`` or ``(None, None)`` when the VEuPathDB
    session cannot be resolved.
    """
    email = await _resolve_veupathdb_email(veupathdb_token, site_id)
    if not email:
        return None, None
    user = await user_repo.get_or_create_by_external_id(email)
    auth_token = create_user_token(user.id)
    return auth_token, email

def _build_success_response(
    veupathdb_token: str,
    auth_token: str | None,
) -> JSONResponse:
    """Build a ``JSONResponse`` that sets both cookies.

    Auth tokens are ONLY set via httpOnly cookies — never exposed in the
    response body — to prevent XSS-based token exfiltration.
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
    user_repo: UserRepo,
    payload: LoginPayload | None = None,
    redirect_to: str | None = Query(None, alias="redirectTo"),
    site_id: str = Query("veupathdb", alias="siteId"),
) -> JSONResponse:
    """Login via VEuPathDB /login, link internal user, and store auth cookies."""
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

    auth_site = get_site(site_id)
    redirect_url = _pick_redirect_url(redirect_to)
    login_payload: dict[str, str] = {
        "email": email,
        "password": password,
        "redirectUrl": redirect_url,
    }

    async with httpx.AsyncClient(
        base_url=auth_site.service_url, follow_redirects=False
    ) as client:
        response = await client.post("/login", json=login_payload)
        set_cookie_headers = response.headers.get_list("set-cookie")
        token = _extract_auth_cookie(set_cookie_headers)

    if not token:
        logger.warning(
            "No non-guest Authorization cookie in VEuPathDB login response "
            "(credentials likely invalid)",
        )
        raise UnauthorizedError(detail="Invalid email or password")

    auth_token, _email = await _link_internal_user(user_repo, token, site_id)
    if not auth_token:
        raise UnauthorizedError(detail="Invalid email or password")
    return _build_success_response(token, auth_token)

@router.post("/logout", response_model=AuthSuccessResponse)
async def logout(
    site_id: str = Query("veupathdb", alias="siteId"),
) -> JSONResponse:
    """Clear local auth cookie and log out of VEuPathDB."""
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
    user_repo: UserRepo,
    site_id: str = Query("veupathdb", alias="siteId"),
) -> JSONResponse:
    """Re-derive the internal ``pathfinder-auth`` token from a live VEuPathDB session.

    Called on page load when the internal token is missing/expired but the
    VEuPathDB ``Authorization`` cookie is still valid.
    """
    veupathdb_token = (
        request.headers.get("X-VEUPATHDB-AUTH")
        or request.headers.get("X-VEUPATHDB-AUTHORIZATION")
        or request.cookies.get("Authorization")
    )
    if not veupathdb_token:
        raise UnauthorizedError(detail="No VEuPathDB session")

    auth_token, _email = await _link_internal_user(user_repo, veupathdb_token, site_id)
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
    """Return current VEuPathDB auth status.

    In test-mode mock runs (``PATHFINDER_CHAT_PROVIDER=mock``), a valid
    ``pathfinder-auth`` cookie is sufficient — the dev-login endpoint
    doesn't create a VEuPathDB session, so we skip the real WDK call.
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
    """Fetch the current user from WDK, returning None on failure."""
    site = get_site(site_id)
    client = get_wdk_client(site.id)
    try:
        raw = await client.get("/users/current")
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        logger.debug("Failed to fetch VEuPathDB auth status", error=str(exc))
        return None
    return _parse_wdk_user(raw)

def _format_auth_status(user: _WDKUserResponse) -> _AuthStatusDict:
    """Format a parsed WDK user into an auth status dict."""
    props = user.properties
    name: str | None = None
    if props.first_name or props.last_name:
        name = " ".join(part for part in (props.first_name, props.last_name) if part)
    name = name or user.email
    return {"signedIn": not user.is_guest, "name": name, "email": user.email}
