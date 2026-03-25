"""VCR-backed integration tests for TemporaryResultsAPI.

Validates create_temporary_result, get_download_url, and get_step_preview
against real WDK responses.

Record:
    WDK_AUTH_EMAIL=<email> WDK_AUTH_PASSWORD=<pw> \
    uv run pytest src/veupath_chatbot/tests/integration/test_vcr_temporary_results.py -v --record-mode=all

Replay:
    uv run pytest src/veupath_chatbot/tests/integration/test_vcr_temporary_results.py -v
"""

import pytest

from veupath_chatbot.integrations.veupathdb.strategy_api import StrategyAPI
from veupath_chatbot.integrations.veupathdb.temporary_results import TemporaryResultsAPI
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    WDKAnswer,
    WDKTemporaryResult,
)
from veupath_chatbot.tests.conftest import create_taxon_step, materialize_step


class TestCreateTemporaryResult:
    """Tests for creating temporary results against real WDK."""

    @pytest.mark.vcr
    async def test_creates_temporary_result(
        self, wdk_api: StrategyAPI, temp_results_api: TemporaryResultsAPI,
    ) -> None:
        step = await create_taxon_step(wdk_api)
        await materialize_step(wdk_api, step.id)

        result = await temp_results_api.create_temporary_result(step_id=step.id)

        assert isinstance(result, WDKTemporaryResult)
        assert result.id != ""


class TestGetStepPreview:
    """Tests for step preview using the standard report endpoint."""

    @pytest.mark.vcr
    async def test_basic_preview(
        self, wdk_api: StrategyAPI, temp_results_api: TemporaryResultsAPI,
    ) -> None:
        step = await create_taxon_step(wdk_api)
        await materialize_step(wdk_api, step.id)

        result = await temp_results_api.get_step_preview(step_id=step.id, limit=5)

        assert isinstance(result, WDKAnswer)

    @pytest.mark.vcr
    async def test_preview_with_attributes(
        self, wdk_api: StrategyAPI, temp_results_api: TemporaryResultsAPI,
    ) -> None:
        step = await create_taxon_step(wdk_api)
        await materialize_step(wdk_api, step.id)

        result = await temp_results_api.get_step_preview(
            step_id=step.id, attributes=["primary_key", "gene_product"],
        )

        assert isinstance(result, WDKAnswer)


class TestGetDownloadUrl:
    """get_download_url constructs URL from the POST response id."""

    @pytest.mark.vcr
    async def test_csv_url(
        self, wdk_api: StrategyAPI, temp_results_api: TemporaryResultsAPI,
    ) -> None:
        step = await create_taxon_step(wdk_api)
        await materialize_step(wdk_api, step.id)

        url = await temp_results_api.get_download_url(
            step_id=step.id, output_format="csv",
        )

        assert "temporary-results/" in url
        assert url.startswith("https://")

    @pytest.mark.vcr
    async def test_json_url(
        self, wdk_api: StrategyAPI, temp_results_api: TemporaryResultsAPI,
    ) -> None:
        step = await create_taxon_step(wdk_api)
        await materialize_step(wdk_api, step.id)

        url = await temp_results_api.get_download_url(
            step_id=step.id, output_format="json",
        )

        assert "temporary-results/" in url

    @pytest.mark.vcr
    async def test_tab_url(
        self, wdk_api: StrategyAPI, temp_results_api: TemporaryResultsAPI,
    ) -> None:
        step = await create_taxon_step(wdk_api)
        await materialize_step(wdk_api, step.id)

        url = await temp_results_api.get_download_url(
            step_id=step.id, output_format="tab",
        )

        assert "temporary-results/" in url

    @pytest.mark.vcr
    async def test_url_with_attributes(
        self, wdk_api: StrategyAPI, temp_results_api: TemporaryResultsAPI,
    ) -> None:
        step = await create_taxon_step(wdk_api)
        await materialize_step(wdk_api, step.id)

        url = await temp_results_api.get_download_url(
            step_id=step.id,
            output_format="csv",
            attributes=["gene_name", "product"],
        )

        assert "temporary-results/" in url
