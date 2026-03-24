"""VCR-backed integration tests for typed WDK client responses.

Verifies that VEuPathDBClient correctly parses REAL WDK REST API
responses into typed Pydantic models. HTTP calls are recorded to
VCR cassettes and replayed on subsequent runs.

Run with recording:
    WDK_AUTH_EMAIL=... WDK_AUTH_PASSWORD=... WDK_TARGET_SITE=plasmodb \
    uv run pytest src/veupath_chatbot/tests/integration/test_wdk_client_typed_responses.py -v --record-mode=all

Replay (default):
    uv run pytest src/veupath_chatbot/tests/integration/test_wdk_client_typed_responses.py -v
"""

import pytest

from veupath_chatbot.integrations.veupathdb.strategy_api import StrategyAPI
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    WDKSearch,
    WDKSearchResponse,
)


class TestClientTypedResponses:
    """Verify that VEuPathDBClient methods parse real WDK responses into typed models."""

    @pytest.mark.vcr
    async def test_get_search_details_returns_wdk_search_response(
        self, wdk_api: StrategyAPI
    ) -> None:
        """get_search_details should return a WDKSearchResponse with typed fields."""
        result = await wdk_api.client.get_search_details(
            "transcript", "GenesByTaxon"
        )

        assert isinstance(result, WDKSearchResponse)
        assert result.search_data.url_segment == "GenesByTaxon"
        assert result.validation.is_valid is True

    @pytest.mark.vcr
    async def test_get_searches_returns_list_of_wdk_search(
        self, wdk_api: StrategyAPI
    ) -> None:
        """get_searches should return a list of WDKSearch models."""
        result = await wdk_api.client.get_searches("transcript")

        assert isinstance(result, list)
        assert len(result) > 0
        for item in result:
            assert isinstance(item, WDKSearch)
        # GenesByTaxon is a fundamental search that must exist on all sites
        url_segments = [s.url_segment for s in result]
        assert "GenesByTaxon" in url_segments

    @pytest.mark.vcr
    async def test_get_search_details_with_params_returns_wdk_search_response(
        self, wdk_api: StrategyAPI
    ) -> None:
        """get_search_details_with_params should return WDKSearchResponse."""
        context = {"organism": '["Plasmodium falciparum 3D7"]'}

        result = await wdk_api.client.get_search_details_with_params(
            "transcript", "GenesByTaxon", context
        )

        assert isinstance(result, WDKSearchResponse)
        assert result.search_data.url_segment == "GenesByTaxon"
