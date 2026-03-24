"""Unit tests for WDK client error handling and edge-case response parsing.

Verifies that VEuPathDBClient raises DataParsingError on malformed data
and that SearchCatalog stores typed models correctly. Uses respx to
provide controlled malformed inputs that cannot come from real WDK.

Happy-path typed response tests live in:
    tests/integration/test_wdk_client_typed_responses.py (VCR-backed)
"""

import contextlib
from collections.abc import Iterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import respx

from veupath_chatbot.integrations.veupathdb.client import VEuPathDBClient
from veupath_chatbot.integrations.veupathdb.discovery import SearchCatalog
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    WDKRecordType,
    WDKSearch,
    WDKSearchResponse,
)
from veupath_chatbot.platform.errors import DataParsingError

_BASE = "https://plasmodb.org/plasmo/service"


# ---------------------------------------------------------------------------
# Inline test data (previously from wdk_responses.py)
# ---------------------------------------------------------------------------


def _searches_response() -> list[dict[str, Any]]:
    return [
        {
            "urlSegment": "GenesByTaxon",
            "fullName": "GeneQuestions.GenesByTaxon",
            "queryName": "GenesByTaxon",
            "displayName": "Organism",
            "shortDisplayName": "Organism",
            "outputRecordClassName": "transcript",
            "paramNames": ["organism"],
            "isAnalyzable": True,
            "isCacheable": True,
            "noSummaryOnSingleRecord": False,
            "defaultSummaryView": "_default",
            "defaultAttributes": ["primary_key", "organism", "gene_product"],
            "defaultSorting": [
                {"attributeName": "organism", "direction": "ASC"},
            ],
            "dynamicAttributes": [],
            "filters": [],
            "groups": [],
            "properties": {},
            "summaryViewPlugins": [],
        },
        {
            "urlSegment": "GenesByTextSearch",
            "fullName": "GeneQuestions.GenesByTextSearch",
            "queryName": "GenesByTextSearch",
            "displayName": "Text search (genes)",
            "shortDisplayName": "Text",
            "outputRecordClassName": "transcript",
            "paramNames": [
                "text_expression",
                "text_fields",
                "text_search_organism",
                "document_type",
            ],
            "isAnalyzable": True,
            "isCacheable": True,
            "noSummaryOnSingleRecord": False,
            "defaultSummaryView": "_default",
            "defaultAttributes": ["primary_key", "gene_product"],
            "defaultSorting": [],
            "dynamicAttributes": [],
            "filters": [],
            "groups": [],
            "properties": {},
            "summaryViewPlugins": [],
        },
        {
            "urlSegment": "boolean_question_TranscriptRecordClasses_TranscriptRecordClass",
            "fullName": "InternalQuestions.boolean_question_TranscriptRecordClasses_TranscriptRecordClass",
            "queryName": "bq_TranscriptRecordClasses_TranscriptRecordClass",
            "displayName": "Combine Gene results",
            "shortDisplayName": "Combine Gene results",
            "outputRecordClassName": "transcript",
            "paramNames": [
                "bq_left_op_TranscriptRecordClasses_TranscriptRecordClass",
                "bq_right_op_TranscriptRecordClasses_TranscriptRecordClass",
                "bq_operator",
            ],
            "isAnalyzable": True,
            "isCacheable": True,
            "noSummaryOnSingleRecord": False,
            "defaultSummaryView": "_default",
            "defaultAttributes": [],
            "defaultSorting": [],
            "dynamicAttributes": [],
            "filters": [],
            "groups": [],
            "properties": {},
            "summaryViewPlugins": [],
            "allowedPrimaryInputRecordClassNames": ["transcript"],
            "allowedSecondaryInputRecordClassNames": ["transcript"],
        },
        {
            "urlSegment": "GenesByOrthologs",
            "fullName": "GeneQuestions.GenesByOrthologs",
            "queryName": "GenesByOrthologs",
            "displayName": "Orthologs",
            "shortDisplayName": "Orthologs",
            "description": "Find genes by ortholog transform",
            "outputRecordClassName": "transcript",
            "paramNames": ["inputStepId", "organism", "isSyntenic"],
            "isAnalyzable": True,
            "isCacheable": True,
            "noSummaryOnSingleRecord": False,
            "defaultSummaryView": "_default",
            "defaultAttributes": ["primary_key", "gene_product"],
            "defaultSorting": [],
            "dynamicAttributes": [],
            "filters": [],
            "groups": [],
            "properties": {},
            "summaryViewPlugins": [],
        },
    ]


def _search_details_response() -> dict[str, Any]:
    return {
        "searchData": {
            "urlSegment": "GenesByTaxon",
            "fullName": "GeneQuestions.GenesByTaxon",
            "queryName": "GenesByTaxon",
            "displayName": "Organism",
            "shortDisplayName": "Organism",
            "summary": "Find all genes from one or more species/organism.",
            "description": "Find all genes from one or more species/organism.",
            "outputRecordClassName": "transcript",
            "isAnalyzable": True,
            "isCacheable": True,
            "noSummaryOnSingleRecord": False,
            "defaultSummaryView": "_default",
            "defaultAttributes": ["primary_key", "organism", "gene_product"],
            "defaultSorting": [
                {"attributeName": "organism", "direction": "ASC"},
            ],
            "paramNames": ["organism"],
            "parameters": [
                {
                    "name": "organism",
                    "displayName": "Organism",
                    "type": "multi-pick-vocabulary",
                    "displayType": "treeBox",
                    "allowEmptyValue": False,
                    "isVisible": True,
                    "isReadOnly": False,
                    "initialDisplayValue": '["Plasmodium falciparum 3D7"]',
                    "minSelectedCount": 1,
                    "maxSelectedCount": -1,
                    "countOnlyLeaves": True,
                    "depthExpanded": 0,
                    "dependentParams": [],
                    "group": "empty",
                    "properties": {},
                    "vocabulary": {
                        "data": {"display": "@@fake@@", "term": "@@fake@@"},
                        "children": [
                            {
                                "data": {
                                    "display": "Plasmodium falciparum 3D7",
                                    "term": "Plasmodium falciparum 3D7",
                                },
                                "children": [],
                            },
                        ],
                    },
                },
            ],
            "dynamicAttributes": [],
            "filters": [],
            "groups": [],
            "properties": {},
            "summaryViewPlugins": [],
        },
        "validation": {
            "level": "DISPLAYABLE",
            "isValid": True,
        },
    }


@contextlib.contextmanager
def _patched_client_deps() -> Iterator[None]:
    """Patch settings and auth context so VEuPathDBClient skips real config."""
    mock_ctx = MagicMock()
    mock_ctx.get.return_value = None
    with (
        patch(
            "veupath_chatbot.integrations.veupathdb.client.get_settings",
            return_value=MagicMock(veupathdb_auth_token=None),
        ),
        patch(
            "veupath_chatbot.integrations.veupathdb.client.veupathdb_auth_token_ctx",
            mock_ctx,
        ),
    ):
        yield


class TestClientErrorHandling:
    """Verify that malformed WDK responses raise DataParsingError.

    These tests MUST use respx (not VCR) because they require controlled
    malformed input that real WDK endpoints would never produce.
    """

    @pytest.mark.anyio
    async def test_malformed_response_raises_data_parsing_error(self) -> None:
        """Completely wrong JSON shape should raise DataParsingError."""
        client = VEuPathDBClient(_BASE)

        with respx.mock(assert_all_called=False) as router:
            router.get(
                f"{_BASE}/record-types/gene/searches/GenesByTaxon",
            ).respond(json={"invalid": "data"})

            with _patched_client_deps(), pytest.raises(DataParsingError):
                await client.get_search_details("gene", "GenesByTaxon")

        await client.close()

    @pytest.mark.anyio
    async def test_missing_required_field_raises_data_parsing_error(self) -> None:
        """searchData missing urlSegment should raise DataParsingError."""
        client = VEuPathDBClient(_BASE)
        bad_json = {
            "searchData": {
                "fullName": "GeneQuestions.GenesByTaxon",
                "displayName": "Organism",
            },
            "validation": {
                "level": "DISPLAYABLE",
                "isValid": True,
            },
        }

        with respx.mock(assert_all_called=False) as router:
            router.get(
                f"{_BASE}/record-types/gene/searches/GenesByTaxon",
            ).respond(json=bad_json)

            with _patched_client_deps(), pytest.raises(DataParsingError):
                await client.get_search_details("gene", "GenesByTaxon")

        await client.close()

    @pytest.mark.anyio
    async def test_error_message_includes_field_path(self) -> None:
        """DataParsingError detail should reference the missing field."""
        client = VEuPathDBClient(_BASE)
        bad_json = {
            "searchData": {
                "fullName": "GeneQuestions.GenesByTaxon",
            },
            "validation": {
                "level": "DISPLAYABLE",
                "isValid": True,
            },
        }

        with respx.mock(assert_all_called=False) as router:
            router.get(
                f"{_BASE}/record-types/gene/searches/GenesByTaxon",
            ).respond(json=bad_json)

            with _patched_client_deps(), pytest.raises(DataParsingError) as exc_info:
                await client.get_search_details("gene", "GenesByTaxon")

        error_str = str(exc_info.value)
        assert "url_segment" in error_str.lower() or "urlSegment" in error_str

        await client.close()

    @pytest.mark.anyio
    async def test_extra_fields_do_not_error(self) -> None:
        """Extra unknown fields should be silently ignored (extra='ignore')."""
        client = VEuPathDBClient(_BASE)
        detail_json = _search_details_response()
        detail_json["searchData"]["totallyNewField"] = "should-be-ignored"
        detail_json["unknownTopLevel"] = 42

        with respx.mock(assert_all_called=False) as router:
            router.get(
                f"{_BASE}/record-types/transcript/searches/GenesByTaxon",
            ).respond(json=detail_json)

            with _patched_client_deps():
                result = await client.get_search_details("transcript", "GenesByTaxon")

        assert isinstance(result, WDKSearchResponse)
        assert result.search_data.url_segment == "GenesByTaxon"

        await client.close()

    @pytest.mark.anyio
    async def test_get_searches_skips_malformed_entries(self) -> None:
        """Malformed list entries should be skipped, good ones kept."""
        client = VEuPathDBClient(_BASE)
        mixed_json = [
            {
                "urlSegment": "GoodSearch",
                "fullName": "GeneQuestions.GoodSearch",
                "outputRecordClassName": "transcript",
            },
            {"bad": "entry"},
        ]

        with respx.mock(assert_all_called=False) as router:
            router.get(
                f"{_BASE}/record-types/gene/searches",
            ).respond(json=mixed_json)

            with _patched_client_deps():
                result = await client.get_searches("gene")

        assert len(result) == 1
        assert isinstance(result[0], WDKSearch)
        assert result[0].url_segment == "GoodSearch"

        await client.close()

    @pytest.mark.anyio
    async def test_get_searches_empty_response(self) -> None:
        """Empty array should return an empty list."""
        client = VEuPathDBClient(_BASE)

        with respx.mock(assert_all_called=False) as router:
            router.get(
                f"{_BASE}/record-types/gene/searches",
            ).respond(json=[])

            with _patched_client_deps():
                result = await client.get_searches("gene")

        assert result == []

        await client.close()

    @pytest.mark.anyio
    async def test_get_searches_non_list_response(self) -> None:
        """Non-list response (e.g. dict) should return empty list."""
        client = VEuPathDBClient(_BASE)

        with respx.mock(assert_all_called=False) as router:
            router.get(
                f"{_BASE}/record-types/gene/searches",
            ).respond(json={"unexpected": "dict"})

            with _patched_client_deps():
                result = await client.get_searches("gene")

        assert result == []

        await client.close()


class TestDiscoveryTypedResponses:
    """Verify that SearchCatalog stores and returns typed models.

    These tests use MagicMock (not respx) for the client -- they test
    the catalog's in-memory storage logic, not HTTP transport.
    """

    @pytest.mark.anyio
    async def test_search_catalog_stores_typed_searches(self) -> None:
        """SearchCatalog.get_searches should return list[WDKSearch]."""
        catalog = SearchCatalog("plasmodb")
        list_json = _searches_response()
        typed_searches = [WDKSearch.model_validate(s) for s in list_json]

        mock_client = MagicMock(spec=VEuPathDBClient)
        mock_client.get_record_types = AsyncMock(
            return_value=[WDKRecordType(url_segment="gene", searches=typed_searches)]
        )
        mock_client.get_searches = AsyncMock(return_value=[])

        await catalog.load(mock_client)
        result = catalog.get_searches("gene")

        assert isinstance(result, list)
        assert len(result) > 0
        for item in result:
            assert isinstance(item, WDKSearch)
        assert result[0].url_segment == "GenesByTaxon"

    @pytest.mark.anyio
    async def test_search_details_through_discovery_typed(self) -> None:
        """SearchCatalog.get_search_details should return WDKSearchResponse."""
        catalog = SearchCatalog("plasmodb")
        list_json = _searches_response()
        detail_json = _search_details_response()
        typed_searches = [WDKSearch.model_validate(s) for s in list_json]

        mock_client = MagicMock(spec=VEuPathDBClient)
        mock_client.get_record_types = AsyncMock(
            return_value=[
                WDKRecordType(url_segment="transcript", searches=typed_searches)
            ]
        )
        mock_client.get_searches = AsyncMock(return_value=[])
        mock_client.get_search_details = AsyncMock(
            return_value=WDKSearchResponse.model_validate(detail_json),
        )

        await catalog.load(mock_client)
        result = await catalog.get_search_details(
            mock_client, "transcript", "GenesByTaxon"
        )

        assert isinstance(result, WDKSearchResponse)
        assert result.search_data.url_segment == "GenesByTaxon"
        assert result.validation.is_valid is True
