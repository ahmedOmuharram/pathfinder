"""A step analysis with no cached result answers 204 with an empty body.

An empty body is not a result. It must not reach a reader as an enrichment
that found nothing.
"""

from __future__ import annotations

import httpx
import pytest

from pathfinder.integrations.veupathdb.analysis_result import (
    WDKAnalysisNotReadyError,
)
from pathfinder.integrations.veupathdb.client import VEuPathDBClient
from pathfinder.platform.errors import AppError
from pathfinder.services.enrichment.types import EnrichmentResult


@pytest.fixture(autouse=True)
def _registered_user(wdk_request_token: str) -> None:
    """These calls address a user's own WDK resources."""
    del wdk_request_token


class _FixedTransport(httpx.AsyncBaseTransport):
    """Answers every request with one canned response."""

    def __init__(self, response: httpx.Response) -> None:
        self._response = response

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        del request
        return self._response


async def _client_answering(response: httpx.Response) -> VEuPathDBClient:
    client = VEuPathDBClient("https://example.invalid/service")
    async with client._client_lock:
        client._client = httpx.AsyncClient(
            base_url=client.base_url, transport=_FixedTransport(response)
        )
    return client


class TestTheResultEndpoint:
    @pytest.mark.asyncio
    async def test_no_content_is_not_a_result(self) -> None:
        client = await _client_answering(httpx.Response(204))

        with pytest.raises(WDKAnalysisNotReadyError):
            await client.get_analysis_result("1", 9, 4)

    @pytest.mark.asyncio
    async def test_a_real_result_still_comes_back(self) -> None:
        body = {"resultData": [{"goId": "GO:0004672", "pValue": "1e-9"}]}
        client = await _client_answering(
            httpx.Response(200, json=body, headers={"content-type": "application/json"})
        )

        assert await client.get_analysis_result("1", 9, 4) == body

    @pytest.mark.asyncio
    async def test_an_empty_result_object_is_still_a_result(self) -> None:
        # A plugin that ran and found nothing sends a body.
        client = await _client_answering(
            httpx.Response(200, json={}, headers={"content-type": "application/json"})
        )

        assert await client.get_analysis_result("1", 9, 4) == {}


class TestTheTwoEmptyResultsAreToldApart:
    def test_the_batch_path_records_it_as_a_failure(self) -> None:
        # The enrichment batch turns an AppError into a result carrying `error`.
        assert isinstance(WDKAnalysisNotReadyError(9, 4), AppError)

    def test_an_enrichment_that_found_nothing_carries_no_error(self) -> None:
        found_nothing = EnrichmentResult(
            analysis_type="go_process", terms=[], total_genes_analyzed=0
        )

        assert found_nothing.error is None

    def test_a_result_that_could_not_be_fetched_carries_the_error(self) -> None:
        could_not_fetch = EnrichmentResult(
            analysis_type="go_process",
            terms=[],
            total_genes_analyzed=0,
            error=str(WDKAnalysisNotReadyError(9, 4)),
        )

        assert could_not_fetch.error is not None
        assert could_not_fetch != EnrichmentResult(
            analysis_type="go_process", terms=[], total_genes_analyzed=0
        )
