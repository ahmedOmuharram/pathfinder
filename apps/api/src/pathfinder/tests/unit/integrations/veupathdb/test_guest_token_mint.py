import httpx
import respx

from pathfinder.integrations.veupathdb.auth_login import (
    extract_any_auth_cookie,
    mint_guest_token,
)
from pathfinder.integrations.veupathdb.factory import get_site

GUEST_JWT = "eyJhbGciOiJFUzUxMiJ9.guest.sig"


def test_extract_any_auth_cookie_accepts_guest_tokens() -> None:
    headers = [
        "wdk_check_auth=;Version=1;Path=/;Max-Age=0",
        f"Authorization={GUEST_JWT};Version=1;Path=/;Max-Age=94608000",
    ]
    assert extract_any_auth_cookie(headers) == GUEST_JWT


def test_extract_any_auth_cookie_none_without_authorization() -> None:
    assert extract_any_auth_cookie(["other=1;Path=/"]) is None


@respx.mock
async def test_mint_guest_token_returns_set_cookie_value() -> None:
    service_url = get_site("veupathdb").service_url
    respx.get(f"{service_url}/users/current").mock(
        return_value=httpx.Response(
            200,
            json={"isGuest": True, "id": 1234},
            headers={
                "Set-Cookie": f"Authorization={GUEST_JWT};Version=1;Path=/;Max-Age=94608000"
            },
        )
    )
    assert await mint_guest_token("veupathdb") == GUEST_JWT


@respx.mock
async def test_mint_guest_token_none_on_http_error() -> None:
    service_url = get_site("veupathdb").service_url
    respx.get(f"{service_url}/users/current").mock(
        return_value=httpx.Response(500, text="boom")
    )
    assert await mint_guest_token("veupathdb") is None


@respx.mock
async def test_mint_guest_token_none_without_cookie() -> None:
    service_url = get_site("veupathdb").service_url
    respx.get(f"{service_url}/users/current").mock(
        return_value=httpx.Response(200, json={"isGuest": True})
    )
    assert await mint_guest_token("veupathdb") is None
