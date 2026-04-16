"""Contract test for the CSRF middleware.

The global ``client`` fixture in :mod:`pathfinder.tests.conftest` sends
``X-Requested-With: XMLHttpRequest`` on **every** request, which hides the
CSRF contract from the rest of the test suite. This file builds its own
``httpx.AsyncClient`` *without* that default header and walks every state-
changing route on the app, asserting that the CSRF middleware rejects it
with 403 before any route handler runs.

If a future route somehow bypasses the middleware — new router mounted
without the app's middleware stack, method spelled differently, etc. —
this contract test fails. It also protects against the opposite class of
bug the frontend just hit: any ``fetch`` path that forgets the header now
surfaces as a 403 here instead of silently failing in the browser.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute

_SAFE_METHODS: frozenset[str] = frozenset({"GET", "HEAD", "OPTIONS"})
_EXPECTED_DETAIL = "Missing required X-Requested-With header"


@pytest.fixture
async def unheaded_client(
    app: FastAPI,
    patch_app_db_engine: None,
    db_cleaner: None,
) -> AsyncIterator[httpx.AsyncClient]:
    """An httpx client with NO default headers — the ``client`` fixture adds
    ``X-Requested-With`` automatically, defeating this contract check.
    """
    del patch_app_db_engine, db_cleaner
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test",
    ) as c:
        yield c


def _state_changing_routes(app: FastAPI) -> list[tuple[str, str]]:
    """Yield ``(method, path)`` for every POST/PUT/PATCH/DELETE on the app."""
    out: list[tuple[str, str]] = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods:
            if method in _SAFE_METHODS:
                continue
            out.append((method, route.path))
    return out


@pytest.mark.asyncio
async def test_every_state_changing_route_rejects_missing_csrf_header(
    unheaded_client: httpx.AsyncClient,
    app: FastAPI,
) -> None:
    """Every POST/PUT/PATCH/DELETE must 403 when CSRF header is absent.

    This is the contract the frontend relies on and conversely must satisfy:
    if the backend silently accepted requests without the header, cross-site
    form submissions could hit state-changing endpoints using a stolen
    same-site cookie. The explicit 403 + detail is also what the frontend
    tests must assert against when verifying its fetch helpers, so a single
    guard covers both sides of the contract.
    """
    routes = _state_changing_routes(app)
    # Guard against the test regressing to an empty sweep: if no routes are
    # discovered, the test would pass vacuously and lose all protection.
    assert len(routes) >= 5, routes

    failures: list[str] = []
    for method, path in routes:
        # Use a syntactically plausible path — path-param placeholders like
        # "{chat_id}" would otherwise 404 at routing time (before the
        # middleware runs in some ASGI stacks). Substituting a valid UUID
        # keeps the request on the real dispatch path.
        concrete = path
        while "{" in concrete:
            start = concrete.index("{")
            end = concrete.index("}", start)
            concrete = (
                concrete[:start]
                + "00000000-0000-0000-0000-000000000000"
                + concrete[end + 1 :]
            )
        resp = await unheaded_client.request(method, concrete)
        if resp.status_code != 403:
            failures.append(
                f"{method} {path} -> {resp.status_code} (expected 403); "
                f"body={resp.text[:200]!r}",
            )
            continue
        body = resp.json()
        if body.get("detail") != _EXPECTED_DETAIL:
            failures.append(
                f"{method} {path} -> 403 but detail={body.get('detail')!r} "
                f"(expected {_EXPECTED_DETAIL!r})",
            )

    assert not failures, "\n".join(failures)


@pytest.mark.asyncio
async def test_safe_methods_bypass_csrf_middleware(
    unheaded_client: httpx.AsyncClient,
) -> None:
    """GET/HEAD/OPTIONS must NOT be gated by the CSRF middleware.

    The CSRF requirement is for state-changing requests only. Read-only
    traffic (health checks, page loads) must pass without the header,
    otherwise even the initial page render would need client-side plumbing.
    """
    resp = await unheaded_client.get("/api/v1/sites")
    # 200 (populated) or 401 (unauthenticated endpoints require auth first);
    # the one thing it MUST NOT be is the CSRF 403.
    assert resp.status_code != 403, resp.text
    if resp.status_code == 403:
        body = resp.json()
        assert body.get("detail") != _EXPECTED_DETAIL
