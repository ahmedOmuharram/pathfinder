"""The per-request ``Authorization`` cookie replaces any jar-held one.

WDK sets an ``Authorization`` cookie on every response and the shared jar
stores it. Two pairs of that name go out, and the server reads the first,
so the request acts as the jar guest instead of the named user.
"""

import httpx

from pathfinder.integrations.veupathdb._http import _inject_auth_cookie


def _cookie_pairs(request: httpx.Request) -> list[str]:
    header = request.headers.get("cookie", "")
    return [p.strip() for p in header.split(";") if p.strip()]


def test_replaces_jar_authorization_cookie() -> None:
    request = httpx.Request(
        "GET",
        "https://plasmodb.org/plasmo/service/users/current",
        headers={"cookie": "Authorization=stale-jar-guest; JSESSIONID=abc123"},
    )
    _inject_auth_cookie(request, "real-user-token")
    pairs = _cookie_pairs(request)
    assert "Authorization=real-user-token" in pairs
    assert "JSESSIONID=abc123" in pairs
    auth_pairs = [p for p in pairs if p.startswith("Authorization=")]
    assert auth_pairs == ["Authorization=real-user-token"]


def test_appends_when_no_authorization_present() -> None:
    request = httpx.Request(
        "GET",
        "https://plasmodb.org/plasmo/service/users/current",
        headers={"cookie": "JSESSIONID=abc123"},
    )
    _inject_auth_cookie(request, "real-user-token")
    pairs = _cookie_pairs(request)
    assert pairs == ["JSESSIONID=abc123", "Authorization=real-user-token"]


def test_sets_cookie_header_when_absent() -> None:
    request = httpx.Request("GET", "https://plasmodb.org/plasmo/service/users/current")
    _inject_auth_cookie(request, "real-user-token")
    assert _cookie_pairs(request) == ["Authorization=real-user-token"]
