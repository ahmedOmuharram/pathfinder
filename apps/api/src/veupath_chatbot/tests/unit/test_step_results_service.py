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
from veupath_chatbot.services.wdk.helpers import DETAIL_ATTRIBUTE_LIMIT
from veupath_chatbot.services.wdk.step_results import StepResultsService


@pytest.fixture
def mock_api() -> MagicMock:
    api = MagicMock()
    api.get_record_type_info = AsyncMock(
        return_value=WDKRecordType.model_validate({
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
        })
    )
    api.get_step_records = AsyncMock(
        return_value=WDKAnswer.model_validate({
            "records": [
                {
                    "id": [{"name": "source_id", "value": "GENE1"}],
                    "attributes": {"gene_name": "foo"},
                },
            ],
            "meta": {"totalCount": 1},
        })
    )
    api.get_column_distribution = AsyncMock(return_value=WDKColumnDistribution())
    api.list_analysis_types = AsyncMock(return_value=[
        WDKStepAnalysisType(name="go-enrichment", display_name="GO Enrichment"),
    ])
    api.get_strategy = AsyncMock(return_value={"stepTree": {}})
    api.get_single_record = AsyncMock(
        return_value=WDKRecordInstance.model_validate({"id": [{"name": "source_id", "value": "GENE1"}]})
    )
    return api


class TestGetAttributes:
    @pytest.mark.asyncio
    async def test_returns_normalized_attributes(self, mock_api: MagicMock) -> None:
        svc = StepResultsService(mock_api, step_id=42, record_type="gene")
        result = await svc.get_attributes()
        assert result["recordType"] == "gene"
        attrs = result["attributes"]
        assert len(attrs) == 2
        assert any(a["name"] == "score" and a["isSortable"] for a in attrs)

    @pytest.mark.asyncio
    async def test_calls_get_record_type_info(self, mock_api: MagicMock) -> None:
        svc = StepResultsService(mock_api, step_id=42, record_type="gene")
        await svc.get_attributes()
        mock_api.get_record_type_info.assert_called_once_with("gene")

    @pytest.mark.asyncio
    async def test_handles_attributes_map_key(self, mock_api: MagicMock) -> None:
        mock_api.get_record_type_info = AsyncMock(
            return_value=WDKRecordType.model_validate({
                "urlSegment": "gene",
                "attributesMap": {
                    "gene_name": {
                        "name": "gene_name",
                        "displayName": "Gene Name",
                        "type": "string",
                    },
                },
            })
        )
        svc = StepResultsService(mock_api, step_id=42, record_type="gene")
        result = await svc.get_attributes()
        assert len(result["attributes"]) == 1


class TestGetRecords:
    @pytest.mark.asyncio
    async def test_returns_paginated_records(self, mock_api: MagicMock) -> None:
        svc = StepResultsService(mock_api, step_id=42, record_type="gene")
        result = await svc.get_records(offset=0, limit=50)
        mock_api.get_step_records.assert_called_once()
        assert len(result.records) == 1
        assert result.meta.total_count == 1

    @pytest.mark.asyncio
    async def test_passes_sorting(self, mock_api: MagicMock) -> None:
        svc = StepResultsService(mock_api, step_id=42, record_type="gene")
        await svc.get_records(sort="score", direction="DESC")
        call_kwargs = mock_api.get_step_records.call_args[1]
        assert call_kwargs["sorting"] == [
            {"attributeName": "score", "direction": "DESC"}
        ]

    @pytest.mark.asyncio
    async def test_passes_attributes(self, mock_api: MagicMock) -> None:
        svc = StepResultsService(mock_api, step_id=42, record_type="gene")
        await svc.get_records(attributes=["gene_name", "score"])
        call_kwargs = mock_api.get_step_records.call_args[1]
        assert call_kwargs["attributes"] == ["gene_name", "score"]

    @pytest.mark.asyncio
    async def test_no_sorting_when_sort_is_none(self, mock_api: MagicMock) -> None:
        svc = StepResultsService(mock_api, step_id=42, record_type="gene")
        await svc.get_records()
        call_kwargs = mock_api.get_step_records.call_args[1]
        assert call_kwargs["sorting"] is None


class TestGetDistribution:
    @pytest.mark.asyncio
    async def test_returns_distribution(self, mock_api: MagicMock) -> None:
        svc = StepResultsService(mock_api, step_id=42, record_type="gene")
        result = await svc.get_distribution("score")
        mock_api.get_column_distribution.assert_called_once_with(42, "score")
        assert isinstance(result, WDKColumnDistribution)
        assert result.histogram == []


class TestListAnalysisTypes:
    @pytest.mark.asyncio
    async def test_returns_types(self, mock_api: MagicMock) -> None:
        svc = StepResultsService(mock_api, step_id=42, record_type="gene")
        result = await svc.list_analysis_types()
        mock_api.list_analysis_types.assert_called_once_with(42)
        types = result["analysisTypes"]
        assert isinstance(types, list)
        assert len(types) == 1
        assert types[0]["name"] == "go-enrichment"


class TestGetStrategy:
    @pytest.mark.asyncio
    async def test_returns_strategy(self, mock_api: MagicMock) -> None:
        svc = StepResultsService(mock_api, step_id=42, record_type="gene")
        result = await svc.get_strategy(100)
        mock_api.get_strategy.assert_called_once_with(100)
        assert result == {"stepTree": {}}


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
            return_value=WDKRecordType.model_validate({
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
                "primaryKeyColumnRefs": ["gene_source_id", "source_id", "project_id"],
            })
        )
        api.get_single_record = AsyncMock(
            return_value=WDKRecordInstance.model_validate({
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
            })
        )
        return api

    @pytest.mark.asyncio
    async def test_passes_in_report_attributes_to_wdk(
        self, detail_api: MagicMock
    ) -> None:
        """Only isInReport=True attributes are requested from WDK."""
        svc = StepResultsService(detail_api, step_id=42, record_type="transcript")
        await svc.get_record_detail(
            [{"name": "source_id", "value": "PF3D7_0102600"}],
            "plasmodb",
        )
        call_kwargs = detail_api.get_single_record.call_args[1]
        requested = call_kwargs["attributes"]
        assert "primary_key" in requested
        assert "gene_product" in requested
        assert "organism" in requested
        assert "overview" not in requested  # isInReport=False

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
        assert result["attributes"]["gene_product"] == "serine/threonine protein kinase"

    @pytest.mark.asyncio
    async def test_never_sends_empty_attributes_to_wdk(
        self, detail_api: MagicMock
    ) -> None:
        """Guard: get_single_record must never receive attributes=[]."""
        svc = StepResultsService(detail_api, step_id=42, record_type="transcript")
        await svc.get_record_detail(
            [{"name": "source_id", "value": "PF3D7_0102600"}],
            "plasmodb",
        )
        call_kwargs = detail_api.get_single_record.call_args[1]
        assert len(call_kwargs["attributes"]) > 0

    @pytest.mark.asyncio
    async def test_caps_attributes_at_limit(self, detail_api: MagicMock) -> None:
        """With many isInReport attributes, only the first N are requested."""
        # Generate 100 isInReport attributes
        many_attrs = [
            {
                "name": f"attr_{i}",
                "displayName": f"Attribute {i}",
                "isInReport": True,
                "isDisplayable": True,
            }
            for i in range(100)
        ]
        detail_api.get_record_type_info = AsyncMock(
            return_value=WDKRecordType.model_validate({
                "urlSegment": "transcript",
                "attributes": many_attrs,
                "primaryKeyColumnRefs": ["source_id"],
            })
        )
        svc = StepResultsService(detail_api, step_id=42, record_type="transcript")
        await svc.get_record_detail(
            [{"name": "source_id", "value": "GENE1"}], "plasmodb"
        )
        call_kwargs = detail_api.get_single_record.call_args[1]
        assert len(call_kwargs["attributes"]) == DETAIL_ATTRIBUTE_LIMIT
