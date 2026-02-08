"""VEuPathDB OAuth login bridge."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from veupath_chatbot.integrations.veupathdb.factory import get_site, get_wdk_client
from veupath_chatbot.platform.config import get_settings
from veupath_chatbot.platform.errors import UnauthorizedError, ValidationError
from veupath_chatbot.platform.logging import get_logger
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


@router.post("/login", response_model=AuthSuccessResponse)
async def login_with_password(
    site_id: str = Query(..., alias="siteId"),
    payload: LoginPayload | None = None,
    redirect_to: str | None = Query(None, alias="redirectTo"),
) -> JSONResponse:
    """Login via VEuPathDB /login and store auth cookie."""
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

    api_response = JSONResponse({"success": True})
    api_response.set_cookie(
        key="Authorization",
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )
    return api_response


@router.post("/token", response_model=AuthSuccessResponse)
async def accept_token(payload: TokenPayload | None = None) -> JSONResponse:
    """Accept a VEuPathDB Authorization token and store it as a cookie."""
    if not payload or not payload.token:
        raise ValidationError(
            detail="Token required",
            errors=[{"path": "token", "message": "Required", "code": "MISSING_FIELD"}],
        )
    token = payload.token
    response = JSONResponse({"success": True})
    response.set_cookie(
        key="Authorization",
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )
    return response


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
    return response


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
    name: str | None = None
    first_value = properties.get("first_name") or properties.get("firstName")
    last_value = properties.get("last_name") or properties.get("lastName")
    first: str | None = str(first_value) if isinstance(first_value, str) else None
    last: str | None = str(last_value) if isinstance(last_value, str) else None
    if first or last:
        name_parts: list[str] = []
        if first:
            name_parts.append(first)
        if last:
            name_parts.append(last)
        name = " ".join(name_parts)
    else:
        full_name_value = properties.get("fullName") or properties.get("name")
        name = str(full_name_value) if isinstance(full_name_value, str) else None
    name = name or email
    return {"signedIn": not is_guest, "name": name, "email": email}
