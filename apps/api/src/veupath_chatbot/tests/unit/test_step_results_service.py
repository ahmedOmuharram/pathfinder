"""Tests for StepResultsService."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from veupath_chatbot.integrations.veupathdb.wdk_models import (
    WDKAnswer,
    WDKColumnDistribution,
    WDKRecordInstance,
    WDKRecordType,
    WDKStepAnalysisType,
)
from veupath_chatbot.services.wdk.step_results import StepResultsService


@pytest.fixture
def mock_api() -> MagicMock:
    api = MagicMock()
    api.get_record_type_info = AsyncMock(
        return_value=WDKRecordType.model_validate(
            {
                "urlSegment": "gene",
                "attributes": [
                    {
                        "name": "gene_name",
                        "displayName": "Gene Name",
                        "type": "string",
                        "isDisplayable": True,
                    },
                    {
                        "name": "score",
                        "displayName": "Score",
                        "type": "number",
                        "isDisplayable": True,
                    },
                ],
            }
        )
    )
    api.get_step_records = AsyncMock(
        return_value=WDKAnswer.model_validate(
            {
                "records": [
                    {
                        "id": [{"name": "source_id", "value": "GENE1"}],
                        "attributes": {"gene_name": "foo"},
                    },
                ],
                "meta": {"totalCount": 1},
            }
        )
    )
    api.get_column_distribution = AsyncMock(return_value=WDKColumnDistribution())
    api.list_analysis_types = AsyncMock(
        return_value=[
            WDKStepAnalysisType(name="go-enrichment", display_name="GO Enrichment"),
        ]
    )
    api.get_single_record = AsyncMock(
        return_value=WDKRecordInstance.model_validate(
            {"id": [{"name": "source_id", "value": "GENE1"}]}
        )
    )
    return api


class TestGetAttributes:
    @pytest.mark.asyncio
    async def test_returns_normalized_attributes(self, mock_api: MagicMock) -> None:
        svc = StepResultsService(mock_api, step_id=42, record_type="gene")
        result = await svc.get_attributes()
        assert result["recordType"] == "gene"
        attrs = result["attributes"]
        assert isinstance(attrs, list)
        assert len(attrs) == 2
        assert any(
            isinstance(a, dict) and a["name"] == "score" and a["isSortable"]
            for a in attrs
        )

    @pytest.mark.asyncio
    async def test_handles_attributes_map_key(self, mock_api: MagicMock) -> None:
        mock_api.get_record_type_info = AsyncMock(
            return_value=WDKRecordType.model_validate(
                {
                    "urlSegment": "gene",
                    "attributesMap": {
                        "gene_name": {
                            "name": "gene_name",
                            "displayName": "Gene Name",
                            "type": "string",
                        },
                    },
                }
            )
        )
        svc = StepResultsService(mock_api, step_id=42, record_type="gene")
        result = await svc.get_attributes()
        assert len(result["attributes"]) == 1


class TestGetRecords:
    @pytest.mark.asyncio
    async def test_returns_paginated_records(self, mock_api: MagicMock) -> None:
        svc = StepResultsService(mock_api, step_id=42, record_type="gene")
        result = await svc.get_records(offset=0, limit=50)
        assert len(result.records) == 1
        assert result.meta.total_count == 1



class TestGetDistribution:
    @pytest.mark.asyncio
    async def test_returns_distribution(self, mock_api: MagicMock) -> None:
        svc = StepResultsService(mock_api, step_id=42, record_type="gene")
        result = await svc.get_distribution("score")
        assert isinstance(result, WDKColumnDistribution)
        assert result.histogram == []


class TestListAnalysisTypes:
    @pytest.mark.asyncio
    async def test_returns_types(self, mock_api: MagicMock) -> None:
        svc = StepResultsService(mock_api, step_id=42, record_type="gene")
        result = await svc.list_analysis_types()
        types = result["analysisTypes"]
        assert isinstance(types, list)
        assert len(types) == 1
        first = types[0]
        assert isinstance(first, dict)
        assert first["name"] == "go-enrichment"


class TestGetRecordDetail:
    """Tests for get_record_detail — must pass actual attribute names to WDK.

    WDK interprets ``"attributes": []`` as "return zero attributes."
    The service must extract attribute names from the record type info
    and pass them to ``get_single_record``.
    """

    @pytest.fixture
    def detail_api(self) -> MagicMock:
        """Mock API with list-format record type info (like real WDK expanded)."""
        api = MagicMock()
        api.get_record_type_info = AsyncMock(
            return_value=WDKRecordType.model_validate(
                {
                    "urlSegment": "transcript",
                    "attributes": [
                        {
                            "name": "primary_key",
                            "displayName": "Gene ID",
                            "isInReport": True,
                            "isDisplayable": True,
                        },
                        {
                            "name": "overview",
                            "displayName": "Overview",
                            "isInReport": False,
                            "isDisplayable": False,
                        },
                        {
                            "name": "gene_product",
                            "displayName": "Product Description",
                            "isInReport": True,
                            "isDisplayable": True,
                        },
                        {
                            "name": "organism",
                            "displayName": "Organism",
                            "isInReport": True,
                            "isDisplayable": True,
                        },
                    ],
                    "primaryKeyColumnRefs": [
                        "gene_source_id",
                        "source_id",
                        "project_id",
                    ],
                }
            )
        )
        api.get_single_record = AsyncMock(
            return_value=WDKRecordInstance.model_validate(
                {
                    "id": [
                        {"name": "gene_source_id", "value": "PF3D7_0102600"},
                        {"name": "source_id", "value": "PF3D7_0102600.1"},
                        {"name": "project_id", "value": "PlasmoDB"},
                    ],
                    "attributes": {
                        "primary_key": "PF3D7_0102600",
                        "gene_product": "serine/threonine protein kinase",
                        "organism": "Plasmodium falciparum 3D7",
                    },
                    "tables": {},
                }
            )
        )
        return api

    @pytest.mark.asyncio
    async def test_response_includes_attribute_names(
        self, detail_api: MagicMock
    ) -> None:
        """Response includes display name map so the frontend can render labels."""
        svc = StepResultsService(detail_api, step_id=42, record_type="transcript")
        result = await svc.get_record_detail(
            [{"name": "source_id", "value": "PF3D7_0102600"}],
            "plasmodb",
        )
        assert "attributeNames" in result
        names = result["attributeNames"]
        assert isinstance(names, dict)
        assert names["primary_key"] == "Gene ID"
        assert names["gene_product"] == "Product Description"
        assert names["organism"] == "Organism"

    @pytest.mark.asyncio
    async def test_response_includes_attributes_from_wdk(
        self, detail_api: MagicMock
    ) -> None:
        """Response includes the populated attributes from WDK."""
        svc = StepResultsService(detail_api, step_id=42, record_type="transcript")
        result = await svc.get_record_detail(
            [{"name": "source_id", "value": "PF3D7_0102600"}],
            "plasmodb",
        )
        assert "attributes" in result
        attrs = result["attributes"]
        assert isinstance(attrs, dict)
        assert attrs["gene_product"] == "serine/threonine protein kinase"

