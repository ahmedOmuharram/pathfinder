"""The analyses list is a summary, not a full instance.

WDK emits two fields per entry. Validating them against the full instance model
made every entry fail, and the per-item suppression turned that into an empty
list rather than an error.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from pathfinder.integrations.veupathdb.client import VEuPathDBClient

_LIVE_ENTRY: dict[str, Any] = {
    "displayName": "Word Enrichment",
    "analysisId": 203635253,
}


class _Listing(httpx.AsyncBaseTransport):
    def __init__(self, body: Any) -> None:
        self._body = body

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            200, json=self._body, headers={"content-type": "application/json"}
        )


async def _client(body: Any) -> VEuPathDBClient:
    client = VEuPathDBClient("https://example.invalid/service")
    async with client._client_lock:
        client._client = httpx.AsyncClient(
            base_url=client.base_url, transport=_Listing(body)
        )
    return client


class TestTheLiveShapeParses:
    @pytest.mark.asyncio
    async def test_an_entry_is_returned(self) -> None:
        client = await _client([_LIVE_ENTRY])

        assert len(await client.list_step_analyses("1", 9)) == 1

    @pytest.mark.asyncio
    async def test_the_analysis_id_survives(self) -> None:
        client = await _client([_LIVE_ENTRY])

        assert (await client.list_step_analyses("1", 9))[0].analysis_id == 203635253

    @pytest.mark.asyncio
    async def test_the_display_name_survives(self) -> None:
        client = await _client([_LIVE_ENTRY])

        entry = (await client.list_step_analyses("1", 9))[0]
        assert entry.display_name == "Word Enrichment"

    @pytest.mark.asyncio
    async def test_several_entries_all_parse(self) -> None:
        client = await _client([_LIVE_ENTRY, {"displayName": "GO", "analysisId": 7}])

        assert len(await client.list_step_analyses("1", 9)) == 2


class TestABadEntryIsStillSkipped:
    @pytest.mark.asyncio
    async def test_an_entry_without_an_id_is_dropped(self) -> None:
        client = await _client([{"displayName": "no id"}, _LIVE_ENTRY])

        assert len(await client.list_step_analyses("1", 9)) == 1

    @pytest.mark.asyncio
    async def test_an_empty_list_is_still_empty(self) -> None:
        client = await _client([])

        assert await client.list_step_analyses("1", 9) == []
