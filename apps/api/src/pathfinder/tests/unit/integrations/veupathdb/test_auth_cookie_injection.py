"""The per-request ``Authorization`` cookie must REPLACE any jar-held one.

WDK sets ``Authorization=<guest jwt>`` on every response — including the
unauthenticated warmup calls a container makes at boot — and the shared
httpx client jar stores it. Appending the real token after jar cookies
sends TWO ``Authorization`` pairs, and Tomcat honors the first: every
request silently acts as the boot-time jar guest no matter which user's
token was injected. (Observed as WDK 403s on strategies the same user
just created via the worker.)
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
