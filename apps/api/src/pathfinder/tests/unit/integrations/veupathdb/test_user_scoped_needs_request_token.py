"""The global service account may not act on a user's WDK resources."""

from __future__ import annotations

from collections.abc import Generator

import httpx
import pytest

from pathfinder.integrations.veupathdb._http import HTTPClient
from pathfinder.platform.context import veupathdb_auth_token_ctx
from pathfinder.platform.errors import ErrorCode, WDKLoginRequiredError

SERVICE_ACCOUNT = "service.account.token"
USER_TOKEN = "registered.user.token"


class _RecordingTransport(httpx.AsyncBaseTransport):
    """Answers every request with 200 and remembers the paths it saw."""

    def __init__(self) -> None:
        self.paths: list[str] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.paths.append(request.url.path)
        return httpx.Response(
            200, json={"id": 1}, headers={"content-type": "application/json"}
        )


async def _client(transport: httpx.AsyncBaseTransport) -> HTTPClient:
    client = HTTPClient(
        base_url="https://example.invalid/service", auth_token=SERVICE_ACCOUNT
    )
    async with client._client_lock:
        client._client = httpx.AsyncClient(
            base_url=client.base_url, transport=transport
        )
    return client


@pytest.fixture(autouse=True)
def _no_request_token() -> Generator[None]:
    reset = veupathdb_auth_token_ctx.set(None)
    yield
    veupathdb_auth_token_ctx.reset(reset)


class TestAUserResourceNeedsTheUsersOwnToken:
    @pytest.mark.asyncio
    async def test_a_step_read_is_refused_and_never_leaves(self) -> None:
        transport = _RecordingTransport()
        client = await _client(transport)

        with pytest.raises(WDKLoginRequiredError) as raised:
            await client.get("/users/1248677203/steps/9")

        assert raised.value.code == ErrorCode.WDK_LOGIN_REQUIRED
        assert raised.value.status == 401
        assert transport.paths == []

    @pytest.mark.asyncio
    async def test_a_step_create_is_refused(self) -> None:
        transport = _RecordingTransport()
        client = await _client(transport)

        with pytest.raises(WDKLoginRequiredError):
            await client.post("/users/1248677203/steps", json={}, idempotent=False)

        assert transport.paths == []

    @pytest.mark.asyncio
    async def test_the_identity_probe_is_refused_too(self) -> None:
        """``/users/current`` resolves a WDK account, so it needs one."""
        transport = _RecordingTransport()
        client = await _client(transport)

        with pytest.raises(WDKLoginRequiredError):
            await client.get("/users/current")

        assert transport.paths == []

    @pytest.mark.asyncio
    async def test_the_users_own_token_is_served(self) -> None:
        transport = _RecordingTransport()
        client = await _client(transport)
        veupathdb_auth_token_ctx.set(USER_TOKEN)

        assert await client.get("/users/1248677203/steps/9") == {"id": 1}
        assert "/service/users/1248677203/steps/9" in transport.paths


class TestUserIndependentReadsStillRunAsTheApplication:
    @pytest.mark.asyncio
    async def test_a_search_listing_is_served(self) -> None:
        transport = _RecordingTransport()
        client = await _client(transport)

        assert await client.get("/record-types/transcript/searches") == {"id": 1}
        assert "/service/record-types/transcript/searches" in transport.paths

    @pytest.mark.asyncio
    async def test_a_search_detail_read_is_served(self) -> None:
        transport = _RecordingTransport()
        client = await _client(transport)

        assert await client.get("/record-types/transcript/searches/GenesByText") == {
            "id": 1
        }
