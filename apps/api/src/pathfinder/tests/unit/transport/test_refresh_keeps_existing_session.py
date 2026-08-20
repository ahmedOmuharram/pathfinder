"""The refresh route re-derives the internal token only when none is valid."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI

from pathfinder.platform.db import get_db_session
from pathfinder.platform.security import create_user_token
from pathfinder.transport.http.routers.veupathdb_auth import router


def _app(monkeypatch: pytest.MonkeyPatch, minted_token: str | None) -> FastAPI:
    async def _link(*args: object, **kwargs: object) -> str | None:
        del args, kwargs
        if minted_token is None:
            message = "refresh must not re-derive a valid session"
            raise AssertionError(message)
        return minted_token

    monkeypatch.setattr(
        "pathfinder.transport.http.routers.veupathdb_auth._link_internal_user",
        _link,
    )

    async def _session() -> AsyncGenerator[None]:
        yield None

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db_session] = _session
    return app


def _client(app: FastAPI) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_a_valid_internal_session_is_kept_not_replaced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _app(monkeypatch, minted_token=None)
    existing = create_user_token(uuid4())
    async with _client(app) as client:
        response = await client.post(
            "/api/v1/veupathdb/auth/refresh",
            cookies={"pathfinder-auth": existing, "Authorization": "veupathdb-jwt"},
        )
    assert response.status_code == 200
    assert response.json() == {"success": True}
    assert "set-cookie" not in response.headers


@pytest.mark.asyncio
async def test_without_an_internal_session_the_token_is_minted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    minted = create_user_token(uuid4())
    app = _app(monkeypatch, minted_token=minted)
    async with _client(app) as client:
        response = await client.post(
            "/api/v1/veupathdb/auth/refresh",
            cookies={"Authorization": "veupathdb-jwt"},
        )
    assert response.status_code == 200
    assert f"pathfinder-auth={minted}" in response.headers.get("set-cookie", "")


@pytest.mark.asyncio
async def test_an_expired_internal_session_is_replaced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    minted = create_user_token(uuid4())
    app = _app(monkeypatch, minted_token=minted)
    async with _client(app) as client:
        response = await client.post(
            "/api/v1/veupathdb/auth/refresh",
            cookies={
                "pathfinder-auth": "not-a-valid-jwt",
                "Authorization": "veupathdb-jwt",
            },
        )
    assert response.status_code == 200
    assert f"pathfinder-auth={minted}" in response.headers.get("set-cookie", "")
