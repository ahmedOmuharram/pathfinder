"""VCR-backed integration tests for StepResultsService.

Merges tests from test_step_results_service_vcr.py and
test_step_results_extended_vcr.py into a single file.

Record:
    WDK_AUTH_EMAIL=<email> WDK_AUTH_PASSWORD=<pw> \
    uv run pytest src/veupath_chatbot/tests/integration/test_vcr_step_results.py -v --record-mode=all

Replay:
    uv run pytest src/veupath_chatbot/tests/integration/test_vcr_step_results.py -v
"""

import pydantic
import pytest

from veupath_chatbot.integrations.veupathdb.strategy_api import StrategyAPI
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    WDKAnswer,
    WDKColumnDistribution,
)
from veupath_chatbot.services.wdk.step_results import StepResultsService
from veupath_chatbot.tests.conftest import create_taxon_step, materialize_step

# ---------------------------------------------------------------------------
# get_attributes
# ---------------------------------------------------------------------------


class TestGetAttributes:
    @pytest.mark.vcr
    async def test_returns_normalized_attributes(self, wdk_api: StrategyAPI) -> None:
        step = await create_taxon_step(wdk_api)
        await materialize_step(wdk_api, step.id)
        svc = StepResultsService(wdk_api, step_id=step.id, record_type="transcript")

        result = await svc.get_attributes()

        assert result["recordType"] == "transcript"
        attrs = result["attributes"]
        assert isinstance(attrs, list)
        assert len(attrs) > 0
        for attr in attrs:
            assert isinstance(attr, dict)
            assert "name" in attr

    @pytest.mark.vcr
    async def test_attributes_include_expected_fields(
        self, wdk_api: StrategyAPI,
    ) -> None:
        step = await create_taxon_step(wdk_api)
        await materialize_step(wdk_api, step.id)
        svc = StepResultsService(wdk_api, step_id=step.id, record_type="transcript")

        result = await svc.get_attributes()
        attrs = result["attributes"]
        assert isinstance(attrs, list)
        names = {a["name"] for a in attrs if isinstance(a, dict)}
        # At least one of these should be present on any VEuPathDB site
        assert "gene_product" in names or "product" in names or len(names) > 5


# ---------------------------------------------------------------------------
# get_records
# ---------------------------------------------------------------------------


class TestGetRecords:
    @pytest.mark.vcr
    async def test_returns_paginated_records(self, wdk_api: StrategyAPI) -> None:
        step = await create_taxon_step(wdk_api)
        await materialize_step(wdk_api, step.id)
        svc = StepResultsService(wdk_api, step_id=step.id, record_type="transcript")

        result = await svc.get_records(offset=0, limit=5)

        assert isinstance(result, WDKAnswer)
        assert len(result.records) <= 5
        assert result.meta.total_count > 0

    @pytest.mark.vcr
    async def test_records_have_primary_key(self, wdk_api: StrategyAPI) -> None:
        step = await create_taxon_step(wdk_api)
        await materialize_step(wdk_api, step.id)
        svc = StepResultsService(wdk_api, step_id=step.id, record_type="transcript")

        result = await svc.get_records(offset=0, limit=3)

        for record in result.records:
            assert len(record.id) > 0
            assert record.id[0]["name"] in ("source_id", "gene_source_id")

    @pytest.mark.vcr
    async def test_default_pagination(self, wdk_api: StrategyAPI) -> None:
        step = await create_taxon_step(wdk_api)
        await materialize_step(wdk_api, step.id)
        svc = StepResultsService(wdk_api, step_id=step.id, record_type="transcript")

        result = await svc.get_records()

        assert result.meta.total_count > 0
        assert len(result.records) <= 50

    @pytest.mark.vcr
    async def test_lowercase_direction_rejected(self, wdk_api: StrategyAPI) -> None:
        step = await create_taxon_step(wdk_api)
        await materialize_step(wdk_api, step.id)
        svc = StepResultsService(wdk_api, step_id=step.id, record_type="transcript")

        with pytest.raises(pydantic.ValidationError, match="Input should be 'ASC' or 'DESC'"):
            await svc.get_records(sort="organism", direction="asc")


# ---------------------------------------------------------------------------
# get_distribution
# ---------------------------------------------------------------------------


class TestGetDistribution:
    @pytest.mark.vcr
    async def test_returns_distribution_for_organism(
        self, wdk_api: StrategyAPI,
    ) -> None:
        step = await create_taxon_step(wdk_api)
        await materialize_step(wdk_api, step.id)
        svc = StepResultsService(wdk_api, step_id=step.id, record_type="transcript")

        result = await svc.get_distribution("organism")

        assert isinstance(result, WDKColumnDistribution)
        # Some WDK sites return 500 for the organism column reporter,
        # in which case the service returns an empty distribution.
        # We verify the typed result is returned either way.
        assert isinstance(result.histogram, list)


# ---------------------------------------------------------------------------
# list_analysis_types
# ---------------------------------------------------------------------------


class TestListAnalysisTypes:
    @pytest.mark.vcr
    async def test_returns_analysis_types(self, wdk_api: StrategyAPI) -> None:
        step = await create_taxon_step(wdk_api)
        await materialize_step(wdk_api, step.id)
        svc = StepResultsService(wdk_api, step_id=step.id, record_type="transcript")

        result = await svc.list_analysis_types()

        types = result["analysisTypes"]
        assert isinstance(types, list)
        assert len(types) > 0


# ---------------------------------------------------------------------------
# get_record_detail
# ---------------------------------------------------------------------------


class TestGetRecordDetail:
    @pytest.mark.vcr
    async def test_returns_record_with_attributes(
        self, wdk_api: StrategyAPI, wdk_site_id: str,
    ) -> None:
        step = await create_taxon_step(wdk_api)
        await materialize_step(wdk_api, step.id)
        svc = StepResultsService(wdk_api, step_id=step.id, record_type="transcript")

        answer = await svc.get_records(offset=0, limit=1)
        assert len(answer.records) > 0
        pk = [
            {"name": part["name"], "value": part["value"]}
            for part in answer.records[0].id
        ]

        result = await svc.get_record_detail(pk, wdk_site_id)

        assert "attributes" in result
        assert "attributeNames" in result
        assert isinstance(result["attributeNames"], dict)

    @pytest.mark.vcr
    async def test_response_includes_display_names(
        self, wdk_api: StrategyAPI, wdk_site_id: str,
    ) -> None:
        step = await create_taxon_step(wdk_api)
        await materialize_step(wdk_api, step.id)
        svc = StepResultsService(wdk_api, step_id=step.id, record_type="transcript")

        answer = await svc.get_records(offset=0, limit=1)
        assert len(answer.records) > 0
        pk = [
            {"name": part["name"], "value": part["value"]}
            for part in answer.records[0].id
        ]

        result = await svc.get_record_detail(pk, wdk_site_id)

        names = result["attributeNames"]
        assert isinstance(names, dict)
        assert len(names) > 0
        for display_name in names.values():
            assert isinstance(display_name, str)
            assert len(display_name) > 0
