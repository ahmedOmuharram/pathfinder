"""A create is not retried, because a second attempt is a second object.

A proxy answers 502 after passing the request upstream, so a retried
``POST /steps`` leaves a step nobody references. Reads and reports stay
retryable: repeating them costs a round trip and nothing else.
"""

from __future__ import annotations

import httpx
import pytest

from pathfinder.integrations.veupathdb._http import HTTPClient
from pathfinder.integrations.veupathdb.delayed_result import DELAYED_RESULT_MESSAGE
from pathfinder.platform.errors import AppError


class _FlakyTransport(httpx.AsyncBaseTransport):
    """Answers 502 until `fail_times` is exhausted, then 200."""

    def __init__(self, fail_times: int, body: object = None) -> None:
        self.fail_times = fail_times
        self.attempts = 0
        self._body = body if body is not None else {"id": 1}

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        del request
        self.attempts += 1
        if self.attempts <= self.fail_times:
            return httpx.Response(502, text="Bad Gateway")
        return httpx.Response(
            200, json=self._body, headers={"content-type": "application/json"}
        )


async def _client(transport: httpx.AsyncBaseTransport) -> HTTPClient:
    client = HTTPClient(base_url="https://example.invalid/service")
    async with client._client_lock:
        client._client = httpx.AsyncClient(
            base_url=client.base_url, transport=transport
        )
    return client


class TestACreateIsAttemptedOnce:
    @pytest.mark.asyncio
    async def test_a_step_create_is_not_retried(self) -> None:
        transport = _FlakyTransport(fail_times=2)
        client = await _client(transport)

        with pytest.raises(AppError):
            await client.post("/users/1/steps", json={}, idempotent=False)

        assert transport.attempts == 1

    @pytest.mark.asyncio
    async def test_a_successful_create_still_returns(self) -> None:
        transport = _FlakyTransport(fail_times=0)
        client = await _client(transport)

        assert await client.post("/users/1/steps", json={}, idempotent=False) == {
            "id": 1
        }


class TestReadsAreStillRetried:
    @pytest.mark.asyncio
    async def test_a_get_recovers_from_a_proxy_error(self) -> None:
        transport = _FlakyTransport(fail_times=2)
        client = await _client(transport)

        assert await client.get("/users/1/steps/9") == {"id": 1}
        assert transport.attempts == 3

    @pytest.mark.asyncio
    async def test_a_report_post_is_retried_by_default(self) -> None:
        # A report POST is a read with a body, and the delayed-result guard
        # depends on it being retried.
        transport = _FlakyTransport(fail_times=2)
        client = await _client(transport)

        await client.post("/users/1/steps/9/reports/standard", json={})

        assert transport.attempts == 3


class TestTheDelayedResultGuardStillRetries:
    @pytest.mark.asyncio
    async def test_the_sentinel_is_retried_on_a_report(self) -> None:
        class _Sentinel(httpx.AsyncBaseTransport):
            def __init__(self) -> None:
                self.attempts = 0

            async def handle_async_request(
                self, request: httpx.Request
            ) -> httpx.Response:
                del request
                self.attempts += 1
                body = (
                    {"status": "accepted", "message": DELAYED_RESULT_MESSAGE}
                    if self.attempts == 1
                    else {"id": 1}
                )
                return httpx.Response(
                    200, json=body, headers={"content-type": "application/json"}
                )

        transport = _Sentinel()
        client = await _client(transport)

        assert await client.post("/users/1/steps/9/reports/standard", json={}) == {
            "id": 1
        }
        assert transport.attempts == 2
