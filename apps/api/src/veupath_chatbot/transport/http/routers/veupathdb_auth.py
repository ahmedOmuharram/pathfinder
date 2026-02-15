"""VEuPathDB OAuth login bridge.

On successful VEuPathDB login the endpoint also creates/looks-up the internal
Pathfinder user (via ``User.external_id = email``) and returns a
``pathfinder-auth`` token so the frontend has a stable identity across sessions.
"""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from veupath_chatbot.integrations.veupathdb.factory import get_site, get_wdk_client
from veupath_chatbot.platform.config import get_settings
from veupath_chatbot.platform.context import veupathdb_auth_token_ctx
from veupath_chatbot.platform.errors import UnauthorizedError, ValidationError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.security import create_user_token
from veupath_chatbot.transport.http.deps import UserRepo
from veupath_chatbot.transport.http.schemas import (
    AuthStatusResponse,
    AuthSuccessResponse,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/veupathdb/auth", tags=["veupathdb-auth"])


class LoginPayload(BaseModel):
    email: str
    password: str


class TokenPayload(BaseModel):
    token: str


def _pick_redirect_url(candidate: str | None) -> str:
    settings = get_settings()
    allowed = settings.cors_origins or []
    if candidate:
        for origin in allowed:
            if candidate.startswith(origin):
                return candidate
    return allowed[0] if allowed else "http://localhost:3000"


def _extract_auth_cookie(set_cookie_headers: list[str]) -> str | None:
    for header in set_cookie_headers:
        if header.startswith("Authorization="):
            value = header.split(";", 1)[0].split("=", 1)[1]
            return value.strip('"')
    return None


async def _resolve_veupathdb_email(veupathdb_token: str) -> str | None:
    """Call VEuPathDB ``/users/current`` and return the user's email (or None)."""
    # Temporarily set the context var so the WDK client picks up the token.
    reset_token = veupathdb_auth_token_ctx.set(veupathdb_token)
    try:
        site = get_site("veupathdb")
        client = get_wdk_client(site.id)
        user = await client.get("/users/current")
    except Exception:
        return None
    finally:
        veupathdb_auth_token_ctx.reset(reset_token)

    if not isinstance(user, dict):
        return None
    is_guest_value = user.get("isGuest")
    is_guest = bool(is_guest_value if isinstance(is_guest_value, bool) else True)
    if is_guest:
        return None
    email_value = user.get("email")
    return str(email_value) if isinstance(email_value, str) else None


async def _link_internal_user(
    user_repo: UserRepo, veupathdb_token: str
) -> tuple[str | None, str | None]:
    """Resolve VEuPathDB identity and create/lookup the internal user.

    Returns ``(auth_token, email)`` or ``(None, None)`` when the VEuPathDB
    session cannot be resolved.
    """
    email = await _resolve_veupathdb_email(veupathdb_token)
    if not email:
        return None, None
    user = await user_repo.get_or_create_by_external_id(email)
    auth_token = create_user_token(user.id)
    return auth_token, email


def _build_success_response(
    veupathdb_token: str,
    auth_token: str | None,
) -> JSONResponse:
    """Build a ``JSONResponse`` that sets both cookies and carries the token.

    :param veupathdb_token: VEuPathDB auth token.
    :param auth_token: str | None.

    """
    body: dict[str, object] = {"success": True}
    if auth_token:
        body["authToken"] = auth_token

    resp = JSONResponse(body)
    resp.set_cookie(
        key="Authorization",
        value=veupathdb_token,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )
    if auth_token:
        resp.set_cookie(
            key="pathfinder-auth",
            value=auth_token,
            httponly=True,
            samesite="lax",
            path="/",
        )
    return resp


@router.post("/login", response_model=AuthSuccessResponse)
async def login_with_password(
    user_repo: UserRepo,
    site_id: str = Query(..., alias="siteId"),
    payload: LoginPayload | None = None,
    redirect_to: str | None = Query(None, alias="redirectTo"),
) -> JSONResponse:
    """Login via VEuPathDB /login, link internal user, and store auth cookies."""
    del site_id  # auth uses VEuPathDB portal
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

    auth_site = get_site("veupathdb")
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
        logger.warning("Authorization cookie missing in VEuPathDB login response")
        raise UnauthorizedError(detail="Login failed")

    auth_token, _email = await _link_internal_user(user_repo, token)
    return _build_success_response(token, auth_token)


@router.post("/token", response_model=AuthSuccessResponse)
async def accept_token(
    user_repo: UserRepo,
    payload: TokenPayload | None = None,
) -> JSONResponse:
    """Accept a VEuPathDB Authorization token and store it as a cookie."""
    if not payload or not payload.token:
        raise ValidationError(
            detail="Token required",
            errors=[{"path": "token", "message": "Required", "code": "MISSING_FIELD"}],
        )
    token = payload.token
    auth_token, _email = await _link_internal_user(user_repo, token)
    return _build_success_response(token, auth_token)


@router.post("/logout", response_model=AuthSuccessResponse)
async def logout() -> JSONResponse:
    """Clear local auth cookie and log out of VEuPathDB."""
    auth_site = get_site("veupathdb")
    async with httpx.AsyncClient(
        base_url=auth_site.service_url, follow_redirects=True
    ) as client:
        try:
            await client.get("/logout")
        except Exception:
            logger.warning("Failed to log out of VEuPathDB")
    response = JSONResponse({"success": True})
    response.delete_cookie(key="Authorization", path="/")
    response.delete_cookie(key="pathfinder-auth", path="/")
    return response


@router.post("/refresh", response_model=AuthSuccessResponse)
async def refresh_internal_auth(
    request: Request,
    user_repo: UserRepo,
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

    auth_token, _email = await _link_internal_user(user_repo, veupathdb_token)
    if not auth_token:
        raise UnauthorizedError(detail="VEuPathDB session expired or invalid")

    body: dict[str, object] = {"success": True, "authToken": auth_token}
    resp = JSONResponse(body)
    resp.set_cookie(
        key="pathfinder-auth",
        value=auth_token,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return resp


@router.get("/status", response_model=AuthStatusResponse)
async def auth_status(
    site_id: str = Query(..., alias="siteId"),
) -> dict[str, object]:
    """Return current VEuPathDB auth status."""
    del site_id  # auth uses VEuPathDB portal
    site = get_site("veupathdb")
    client = get_wdk_client(site.id)
    try:
        user = await client.get("/users/current")
    except Exception:
        return {"signedIn": False, "name": None, "email": None}

    from veupath_chatbot.platform.types import as_json_object

    if not isinstance(user, dict):
        return {"signedIn": False, "name": None, "email": None}
    user_obj = as_json_object(user)
    is_guest_value = user_obj.get("isGuest")
    is_guest = bool(is_guest_value if isinstance(is_guest_value, bool) else True)
    email_value = user_obj.get("email")
    email: str | None = str(email_value) if isinstance(email_value, str) else None
    properties_value = user_obj.get("properties")
    properties: dict[str, object] = {}
    if isinstance(properties_value, dict):
        properties = {str(k): v for k, v in properties_value.items()}
    first_value = properties.get("firstName")
    last_value = properties.get("lastName")
    first: str | None = str(first_value) if isinstance(first_value, str) else None
    last: str | None = str(last_value) if isinstance(last_value, str) else None
    name: str | None = None
    if first or last:
        name = " ".join(part for part in (first, last) if part)
    name = name or email
    return {"signedIn": not is_guest, "name": name, "email": email}
