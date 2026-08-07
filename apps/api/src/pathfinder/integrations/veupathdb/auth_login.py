from __future__ import annotations

import base64
import binascii
import json

import httpx

from pathfinder.integrations.veupathdb.factory import get_site

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
    except ValueError, binascii.Error:
        return True
    return bool(payload.get("is_guest", False))


def extract_auth_cookie(set_cookie_headers: list[str]) -> str | None:
    """Return the first non-guest ``Authorization`` cookie value, or None."""
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


async def password_login(
    site_id: str, email: str, password: str, *, redirect_url: str = "/"
) -> str | None:
    """Log in to a VEuPathDB site with email/password and return the non-guest
    WDK ``Authorization`` token (the value that feeds ``veupathdb_auth_token_ctx``),
    or None when the credentials are rejected."""

    site = get_site(site_id)
    payload = {"email": email, "password": password, "redirectUrl": redirect_url}
    async with httpx.AsyncClient(
        base_url=site.service_url, follow_redirects=False
    ) as client:
        response = await client.post("/login", json=payload)
        return extract_auth_cookie(response.headers.get_list("set-cookie"))


def extract_any_auth_cookie(set_cookie_headers: list[str]) -> str | None:
    """Return the first ``Authorization`` cookie value, guest or not."""
    for header in set_cookie_headers:
        if not header.startswith("Authorization="):
            continue
        value = header.split(";", 1)[0].split("=", 1)[1].strip('"')
        if value:
            return value
    return None


async def mint_guest_token(site_id: str) -> str | None:
    """Create a fresh WDK guest identity and return its ``Authorization`` token.

    An unauthenticated ``GET /users/current`` makes WDK mint a guest user and
    hand back its long-lived JWT via ``Set-Cookie``. VEuPathDB auth is
    BRC-central, so a guest token minted on one site is valid on all of them.
    Returns None when WDK is unreachable or responds without the cookie.
    """
    site = get_site(site_id)
    try:
        async with httpx.AsyncClient(
            base_url=site.service_url, follow_redirects=True, timeout=15.0
        ) as client:
            response = await client.get("/users/current")
            response.raise_for_status()
    except httpx.HTTPError:
        return None
    return extract_any_auth_cookie(response.headers.get_list("set-cookie"))
