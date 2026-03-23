"""Integration boundary tests for typed WDK client responses.

Verifies that VEuPathDBClient correctly parses WDK REST API responses
into typed Pydantic models, and raises DataParsingError on malformed data.
Uses respx to mock HTTP responses.
"""

import contextlib
from collections.abc import Iterator
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
from veupath_chatbot.tests.fixtures.wdk_responses import (
    search_details_response,
    searches_response,
)

_BASE = "https://plasmodb.org/plasmo/service"


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


class TestClientTypedResponses:
    """Verify that VEuPathDBClient methods parse responses into typed models."""

    @pytest.mark.anyio
    async def test_get_search_details_returns_wdk_search_response(self) -> None:
        """get_search_details should return a WDKSearchResponse with typed fields."""
        client = VEuPathDBClient(_BASE)
        detail_json = search_details_response()

        with respx.mock(assert_all_called=False) as router:
            router.get(
                f"{_BASE}/record-types/transcript/searches/GenesByTaxon",
            ).respond(json=detail_json)

            with _patched_client_deps():
                result = await client.get_search_details("transcript", "GenesByTaxon")

        assert isinstance(result, WDKSearchResponse)
        assert result.search_data.url_segment == "GenesByTaxon"
        assert result.validation.is_valid is True

        await client.close()

    @pytest.mark.anyio
    async def test_get_searches_returns_list_of_wdk_search(self) -> None:
        """get_searches should return a list of WDKSearch models."""
        client = VEuPathDBClient(_BASE)
        list_json = searches_response()

        with respx.mock(assert_all_called=False) as router:
            router.get(
                f"{_BASE}/record-types/transcript/searches",
            ).respond(json=list_json)

            with _patched_client_deps():
                result = await client.get_searches("transcript")

        assert isinstance(result, list)
        assert len(result) == len(list_json)
        for item in result:
            assert isinstance(item, WDKSearch)
        assert result[0].url_segment == "GenesByTaxon"

        await client.close()

    @pytest.mark.anyio
    async def test_get_search_details_with_params_returns_wdk_search_response(
        self,
    ) -> None:
        """get_search_details_with_params should return WDKSearchResponse."""
        client = VEuPathDBClient(_BASE)
        detail_json = search_details_response()
        context = {"organism": '["Plasmodium falciparum 3D7"]'}

        with respx.mock(assert_all_called=False) as router:
            router.post(
                f"{_BASE}/record-types/transcript/searches/GenesByTaxon",
            ).respond(json=detail_json)

            with _patched_client_deps():
                result = await client.get_search_details_with_params(
                    "transcript", "GenesByTaxon", context
                )

        assert isinstance(result, WDKSearchResponse)
        assert result.search_data.url_segment == "GenesByTaxon"

        await client.close()


class TestClientErrorHandling:
    """Verify that malformed WDK responses raise DataParsingError."""

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
        detail_json = search_details_response()
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
    """Verify that SearchCatalog stores and returns typed models."""

    @pytest.mark.anyio
    async def test_search_catalog_stores_typed_searches(self) -> None:
        """SearchCatalog.get_searches should return list[WDKSearch]."""
        catalog = SearchCatalog("plasmodb")
        list_json = searches_response()
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
        list_json = searches_response()
        detail_json = search_details_response()
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
