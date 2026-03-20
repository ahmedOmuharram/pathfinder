"""Extended security tests — edge cases for JWT handling, token parsing, and auth flow.

Focuses on:
- Cookie token vs Authorization header priority
- Bearer prefix edge cases (case sensitivity, empty token, extra spaces)
- JWT algorithm confusion
- Token with extra/unexpected claims
- Negative expiry edge cases
"""

import base64
import json
import time
from uuid import uuid4

import jwt
import pytest
from starlette.requests import Request

from veupath_chatbot.platform.config import get_settings
from veupath_chatbot.platform.context import user_id_ctx
from veupath_chatbot.platform.errors import UnauthorizedError
from veupath_chatbot.platform.security import (
    create_user_token,
    get_current_user,
    get_optional_user,
)


def _make_request(
    *, cookie: str | None = None, auth_header: str | None = None
) -> Request:

    headers: list[tuple[bytes, bytes]] = []
    if auth_header:
        headers.append((b"authorization", auth_header.encode()))
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "query_string": b"",
        "headers": headers,
    }
    return Request(scope)


class TestBearerPrefixEdgeCases:
    """Edge cases around the 'Bearer xxx' parsing in get_optional_user."""

    async def test_bearer_case_insensitive(self):
        """'BEARER', 'bearer', 'Bearer' should all work via header fallback."""
        user_id = uuid4()
        token = create_user_token(user_id)
        for prefix in ("Bearer", "bearer", "BEARER", "bEaReR"):
            request = _make_request(auth_header=f"{prefix} {token}")
            result = await get_optional_user(request, cookie_token=None)
            assert result == user_id, f"Failed for prefix: {prefix}"

    async def test_bearer_with_multiple_spaces(self):
        """'Bearer  token' — the partition on ' ' should leave extra space in token."""
        user_id = uuid4()
        token = create_user_token(user_id)
        # "Bearer  <token>" -> partition(" ") -> ("Bearer", " ", " <token>")
        # token becomes " <token>" which is invalid as a JWT
        request = _make_request(auth_header=f"Bearer  {token}")
        result = await get_optional_user(request, cookie_token=None)
        # The leading space makes jwt.decode fail, returns None
        assert result is None

    async def test_empty_bearer_returns_none(self):
        """'Bearer ' (with trailing space but no token) should return None."""
        request = _make_request(auth_header="Bearer ")
        result = await get_optional_user(request, cookie_token=None)
        assert result is None

    async def test_just_bearer_no_space(self):
        """'Bearer' (no space, no token) — partition finds no space."""
        request = _make_request(auth_header="Bearer")
        result = await get_optional_user(request, cookie_token=None)
        # partition(" ") on "Bearer" -> ("Bearer", "", "") so scheme="Bearer", token=""
        # scheme.lower() == "bearer" is True, token is "" -> return None
        assert result is None


class TestCookieVsHeaderPriority:
    """Cookie token should take priority over Authorization header."""

    async def test_cookie_wins_over_header(self):
        cookie_user = uuid4()
        header_user = uuid4()
        cookie_token = create_user_token(cookie_user)
        header_token = create_user_token(header_user)
        request = _make_request(auth_header=f"Bearer {header_token}")
        result = await get_optional_user(request, cookie_token=cookie_token)
        assert result == cookie_user

    async def test_invalid_cookie_does_not_fall_through_to_header(self):
        """If cookie is provided but invalid, the code still tries it (won't use header).

        BUG: When cookie_token is "bad-token", str(cookie_token) is truthy,
        so token_header = "bad-token" and the Authorization header is never checked.
        This is actually correct behavior — cookie takes precedence.
        """
        header_user = uuid4()
        header_token = create_user_token(header_user)
        request = _make_request(auth_header=f"Bearer {header_token}")
        result = await get_optional_user(request, cookie_token="bad-token")
        # cookie_token is truthy -> uses "bad-token" -> fails -> returns None
        # Does NOT fall through to header (expected: cookie has priority)
        assert result is None


class TestJWTAlgorithmConfusion:
    """Verify that algorithm confusion attacks are prevented."""

    async def test_none_algorithm_rejected(self):
        """JWT with alg=none should be rejected."""
        user_id = uuid4()
        # Encode without a secret (alg=none)
        # PyJWT doesn't allow alg=none easily, but we can craft the token manually
        header = base64.urlsafe_b64encode(
            json.dumps({"alg": "none", "typ": "JWT"}).encode()
        ).rstrip(b"=")
        payload = base64.urlsafe_b64encode(
            json.dumps({"sub": str(user_id), "exp": int(time.time()) + 3600}).encode()
        ).rstrip(b"=")
        fake_token = f"{header.decode()}.{payload.decode()}."
        request = _make_request()
        result = await get_optional_user(request, cookie_token=fake_token)
        assert result is None

    async def test_hs384_rejected(self):
        """Token signed with HS384 should be rejected (only HS256 allowed)."""
        user_id = uuid4()
        settings = get_settings()
        token = jwt.encode(
            {"sub": str(user_id), "exp": int(time.time()) + 3600},
            settings.api_secret_key,
            algorithm="HS384",
        )
        request = _make_request()
        result = await get_optional_user(request, cookie_token=token)
        assert result is None


class TestJWTClaimEdgeCases:
    """Edge cases around JWT claims."""

    async def test_non_uuid_sub_returns_none(self):
        """'sub' claim is a plain string, not a valid UUID."""
        settings = get_settings()
        token = jwt.encode(
            {"sub": "not-a-uuid", "exp": int(time.time()) + 3600},
            settings.api_secret_key,
            algorithm="HS256",
        )
        request = _make_request()
        result = await get_optional_user(request, cookie_token=token)
        assert result is None

    async def test_no_exp_claim_rejects_token(self):
        """Token without 'exp' must be rejected (require=["exp","sub"])."""
        settings = get_settings()
        user_id = uuid4()
        token = jwt.encode(
            {"sub": str(user_id)},  # no exp
            settings.api_secret_key,
            algorithm="HS256",
        )
        request = _make_request()
        result = await get_optional_user(request, cookie_token=token)
        assert result is None

    async def test_extra_claims_ignored(self):
        """Extra claims in the payload should not affect authentication."""
        settings = get_settings()
        user_id = uuid4()
        token = jwt.encode(
            {
                "sub": str(user_id),
                "exp": int(time.time()) + 3600,
                "role": "admin",
                "name": "Test User",
            },
            settings.api_secret_key,
            algorithm="HS256",
        )
        request = _make_request()
        result = await get_optional_user(request, cookie_token=token)
        assert result == user_id

    async def test_expired_token_returns_none(self):
        user_id = uuid4()
        token = create_user_token(user_id, expires_in=-100)
        request = _make_request()
        result = await get_optional_user(request, cookie_token=token)
        assert result is None

    async def test_user_id_context_set_on_success(self):
        user_id = uuid4()
        token = create_user_token(user_id)
        request = _make_request()
        await get_optional_user(request, cookie_token=token)
        assert user_id_ctx.get() == user_id

    async def test_user_id_context_not_set_on_failure(self):
        """Failed auth should not set the context var.

        NOTE: We can't definitively test "not set" since context vars persist
        across async tasks in the same context. We just check that the function
        returns None.
        """
        request = _make_request()
        result = await get_optional_user(request, cookie_token="invalid")
        assert result is None


class TestCreateUserToken:
    def test_zero_expiry(self):
        """Token with 0-second expiry should be valid at the instant of creation."""
        user_id = uuid4()
        token = create_user_token(user_id, expires_in=0)
        settings = get_settings()
        # Might be expired by the time we decode (race), so just check structure
        try:
            payload = jwt.decode(token, settings.api_secret_key, algorithms=["HS256"])
            assert payload["sub"] == str(user_id)
        except jwt.ExpiredSignatureError:
            pass  # Race condition — token expired between creation and decode

    def test_large_expiry(self):
        """Very large expiry should work."""
        user_id = uuid4()
        token = create_user_token(user_id, expires_in=365 * 24 * 3600)
        settings = get_settings()
        payload = jwt.decode(token, settings.api_secret_key, algorithms=["HS256"])
        assert payload["sub"] == str(user_id)

    def test_token_is_string(self):
        token = create_user_token(uuid4())
        assert isinstance(token, str)
        # JWT has three dot-separated parts
        parts = token.split(".")
        assert len(parts) == 3


class TestGetCurrentUser:
    async def test_none_raises_unauthorized(self):
        with pytest.raises(UnauthorizedError):
            await get_current_user(None)

    async def test_valid_uuid_passes(self):
        user_id = uuid4()
        result = await get_current_user(user_id)
        assert result == user_id
