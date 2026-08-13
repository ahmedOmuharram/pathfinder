"""Tests that the HTTP client starts a new WDK session when the auth token
changes.

One client per site serves every task, so the clients share a cookie jar.
"""

from __future__ import annotations

from typing import Any, ClassVar

import httpx
import pytest

from pathfinder.integrations.veupathdb._http import HTTPClient


class _CapturingTransport(httpx.AsyncBaseTransport):
    """Async transport that records every request."""

    requests: ClassVar[list[httpx.Request]] = []

    async def handle_async_request(
        self,
        request: httpx.Request,
    ) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(
            200,
            json={},
            headers={"content-type": "application/json"},
        )


@pytest.fixture(autouse=True)
def _reset() -> None:
    _CapturingTransport.requests.clear()


async def _build_client_with_transport(
    client: HTTPClient,
    transport: _CapturingTransport,
) -> None:
    """Give the client a transport that records the outgoing requests."""
    async with client._client_lock:
        client._client = httpx.AsyncClient(
            base_url=client.base_url,
            transport=transport,
            follow_redirects=True,
        )


@pytest.mark.asyncio
async def test_reinits_when_token_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two tokens on one client produce two session init calls."""
    transport = _CapturingTransport()
    client = HTTPClient(base_url="https://plasmodb.org/plasmo/service")
    await _build_client_with_transport(client, transport)

    monkeypatch.setattr(
        "pathfinder.integrations.veupathdb._http.veupathdb_auth_token_ctx",
        _ConstCtx("token-A"),
    )
    await client._request_attempt("GET", "/ping")

    monkeypatch.setattr(
        "pathfinder.integrations.veupathdb._http.veupathdb_auth_token_ctx",
        _ConstCtx("token-B"),
    )
    await client._request_attempt("GET", "/ping")

    init_paths = [r for r in _CapturingTransport.requests if "/app" in str(r.url)]
    assert len(init_paths) == 2, (
        f"Expected 2 JSESSIONID init calls (one per token), "
        f"got {len(init_paths)}: {[str(r.url) for r in _CapturingTransport.requests]}"
    )


@pytest.mark.asyncio
async def test_does_not_reinit_when_token_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One token produces one session init call."""
    transport = _CapturingTransport()
    client = HTTPClient(base_url="https://plasmodb.org/plasmo/service")
    await _build_client_with_transport(client, transport)

    monkeypatch.setattr(
        "pathfinder.integrations.veupathdb._http.veupathdb_auth_token_ctx",
        _ConstCtx("token-same"),
    )
    await client._request_attempt("GET", "/ping")
    await client._request_attempt("GET", "/ping")

    init_paths = [r for r in _CapturingTransport.requests if "/app" in str(r.url)]
    assert len(init_paths) == 1, (
        f"Expected 1 JSESSIONID init call, got {len(init_paths)}"
    )


@pytest.mark.asyncio
async def test_clears_jsessionid_cookie_on_reinit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A new session removes the session cookie of the previous token."""
    transport = _CapturingTransport()
    client = HTTPClient(base_url="https://plasmodb.org/plasmo/service")
    await _build_client_with_transport(client, transport)
    client._client.cookies.set(
        "JSESSIONID",
        "stale-session-A",
        domain="plasmodb.org",
    )

    monkeypatch.setattr(
        "pathfinder.integrations.veupathdb._http.veupathdb_auth_token_ctx",
        _ConstCtx("token-B"),
    )
    await client._request_attempt("GET", "/ping")

    assert (
        client._client.cookies.get(
            "JSESSIONID",
        )
        != "stale-session-A"
    ), (
        "JSESSIONID from the previous token must not leak into the new "
        "token's request chain. Either the jar should be cleared or "
        "_init_wdk_session should replace the cookie entirely."
    )


class _ConstCtx:
    """A read-only stand-in for the auth token context variable."""

    def __init__(self, value: str | None) -> None:
        self._value = value

    def get(self) -> str | None:
        return self._value

    def set(self, *_: Any, **__: Any) -> Any:
        msg = "test-only ctxvar stub; use monkeypatch to swap"
        raise NotImplementedError(msg)
