"""Unit tests for the security module (auth, JWT, rate limiting)."""

import time
from uuid import uuid4

import jwt
import pytest
from fastapi import Request

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
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "query_string": b"",
        "headers": [],
    }
    if auth_header:
        scope["headers"] = [(b"authorization", auth_header.encode())]
    return Request(scope)


class TestCreateUserToken:
    def test_creates_valid_jwt(self):
        user_id = uuid4()
        token = create_user_token(user_id)
        settings = get_settings()
        payload = jwt.decode(token, settings.api_secret_key, algorithms=["HS256"])
        assert payload["sub"] == str(user_id)
        assert "exp" in payload

    def test_custom_expiry(self):
        user_id = uuid4()
        token = create_user_token(user_id, expires_in=60)
        settings = get_settings()
        payload = jwt.decode(token, settings.api_secret_key, algorithms=["HS256"])
        assert payload["exp"] <= int(time.time()) + 60

    def test_expired_token_raises(self):
        user_id = uuid4()
        token = create_user_token(user_id, expires_in=-10)
        settings = get_settings()
        with pytest.raises(jwt.ExpiredSignatureError):
            jwt.decode(token, settings.api_secret_key, algorithms=["HS256"])


class TestGetOptionalUser:
    @pytest.mark.asyncio
    async def test_valid_cookie_token(self):
        user_id = uuid4()
        token = create_user_token(user_id)
        request = _make_request()
        result = await get_optional_user(request, cookie_token=token)
        assert result == user_id

    @pytest.mark.asyncio
    async def test_valid_bearer_header_fallback(self):
        user_id = uuid4()
        token = create_user_token(user_id)
        request = _make_request(auth_header=f"Bearer {token}")
        result = await get_optional_user(request, cookie_token=None)
        assert result == user_id

    @pytest.mark.asyncio
    async def test_raw_token_in_header(self):
        user_id = uuid4()
        token = create_user_token(user_id)
        request = _make_request(auth_header=token)
        result = await get_optional_user(request, cookie_token=None)
        assert result == user_id

    @pytest.mark.asyncio
    async def test_no_token_returns_none(self):
        request = _make_request()
        result = await get_optional_user(request, cookie_token=None)
        assert result is None

    @pytest.mark.asyncio
    async def test_expired_token_returns_none(self):
        user_id = uuid4()
        token = create_user_token(user_id, expires_in=-10)
        request = _make_request()
        result = await get_optional_user(request, cookie_token=token)
        assert result is None

    @pytest.mark.asyncio
    async def test_malformed_token_returns_none(self):
        request = _make_request()
        result = await get_optional_user(request, cookie_token="not-a-jwt")
        assert result is None

    @pytest.mark.asyncio
    async def test_wrong_secret_returns_none(self):
        user_id = uuid4()
        token = jwt.encode(
            {"sub": str(user_id), "exp": int(time.time()) + 3600},
            "wrong-secret-key-that-is-long-enough",
            algorithm="HS256",
        )
        request = _make_request()
        result = await get_optional_user(request, cookie_token=token)
        assert result is None

    @pytest.mark.asyncio
    async def test_missing_sub_claim_returns_none(self):
        settings = get_settings()
        token = jwt.encode(
            {"exp": int(time.time()) + 3600},
            settings.api_secret_key,
            algorithm="HS256",
        )
        request = _make_request()
        result = await get_optional_user(request, cookie_token=token)
        assert result is None

    @pytest.mark.asyncio
    async def test_invalid_uuid_sub_returns_none(self):
        settings = get_settings()
        token = jwt.encode(
            {"sub": "not-a-uuid", "exp": int(time.time()) + 3600},
            settings.api_secret_key,
            algorithm="HS256",
        )
        request = _make_request()
        result = await get_optional_user(request, cookie_token=token)
        assert result is None

    @pytest.mark.asyncio
    async def test_sets_user_id_context_var(self):
        user_id = uuid4()
        token = create_user_token(user_id)
        request = _make_request()
        await get_optional_user(request, cookie_token=token)
        assert user_id_ctx.get() == user_id

    @pytest.mark.asyncio
    async def test_cookie_takes_priority_over_header(self):
        cookie_user = uuid4()
        header_user = uuid4()
        cookie_token = create_user_token(cookie_user)
        header_token = create_user_token(header_user)
        request = _make_request(auth_header=f"Bearer {header_token}")
        result = await get_optional_user(request, cookie_token=cookie_token)
        assert result == cookie_user

    @pytest.mark.asyncio
    async def test_bearer_prefix_without_token_returns_none(self):
        request = _make_request(auth_header="Bearer ")
        result = await get_optional_user(request, cookie_token=None)
        assert result is None


class TestGetCurrentUser:
    @pytest.mark.asyncio
    async def test_returns_user_when_authenticated(self):
        user_id = uuid4()
        result = await get_current_user(user_id)
        assert result == user_id

    @pytest.mark.asyncio
    async def test_raises_unauthorized_when_none(self):
        with pytest.raises(UnauthorizedError):
            await get_current_user(None)
