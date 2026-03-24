"""Unit tests for site-search Pydantic models, HTML stripping, SiteInfo,
SiteSearchClient retry/error logic, and SiteRouter integration.

HTTP contract compliance tests live in
tests/integration/test_site_search_contract.py (VCR-backed).
"""

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx

from veupath_chatbot.integrations.veupathdb.site_router import SiteInfo, SiteRouter
from veupath_chatbot.integrations.veupathdb.site_search_client import (
    DocumentTypeFilter,
    SiteSearchCategory,
    SiteSearchClient,
    SiteSearchDocument,
    SiteSearchDocumentType,
    SiteSearchDocumentTypeField,
    SiteSearchResponse,
)
from veupath_chatbot.platform.errors import AppError
from veupath_chatbot.platform.text import strip_html_tags


class TestSiteSearchModels:
    """Pydantic models aligned with SiteSearch/Types.ts from web-monorepo."""

    def test_document_parses_from_live_shape(self) -> None:
        raw = {
            "documentType": "gene",
            "primaryKey": ["PF3D7_0523000"],
            "wdkPrimaryKeyString": "PF3D7_0523000",
            "hyperlinkName": "protein kinase",
            "organism": ["Plasmodium falciparum 3D7"],
            "score": 43.7,
            "summaryFieldData": {
                "TEXT__gene_product": "protein kinase",
                "TEXT__gene_organism_full": "Plasmodium falciparum 3D7",
            },
            "foundInFields": {
                "TEXT__gene_product": ["protein <em>kinase</em>"],
            },
        }
        doc = SiteSearchDocument.model_validate(raw)
        assert doc.document_type == "gene"
        assert doc.primary_key == ["PF3D7_0523000"]
        assert doc.wdk_primary_key_string == "PF3D7_0523000"
        assert doc.organism == ["Plasmodium falciparum 3D7"]
        assert doc.score == 43.7
        assert doc.summary_field_data["TEXT__gene_product"] == "protein kinase"
        assert doc.found_in_fields["TEXT__gene_product"] == ["protein <em>kinase</em>"]

    def test_document_organism_coerces_list(self) -> None:
        doc = SiteSearchDocument.model_validate({"organism": ["Pf 3D7"]})
        assert doc.organism == ["Pf 3D7"]

    def test_document_organism_coerces_string(self) -> None:
        doc = SiteSearchDocument.model_validate({"organism": "Pf 3D7"})
        assert doc.organism == ["Pf 3D7"]

    def test_document_organism_handles_missing(self) -> None:
        doc = SiteSearchDocument.model_validate({})
        assert doc.organism == []

    def test_document_summary_field_data_str(self) -> None:
        doc = SiteSearchDocument.model_validate(
            {"summaryFieldData": {"TEXT__gene_product": "kinase"}}
        )
        assert doc.summary_field_data["TEXT__gene_product"] == "kinase"

    def test_document_summary_field_data_list(self) -> None:
        doc = SiteSearchDocument.model_validate(
            {"summaryFieldData": {"TEXT__gene_product": ["kinase", "protein"]}}
        )
        assert doc.summary_field_data["TEXT__gene_product"] == ["kinase", "protein"]

    def test_response_parses_full_shape(self) -> None:
        raw = {
            "searchResults": {
                "totalCount": 42,
                "documents": [
                    {
                        "documentType": "gene",
                        "primaryKey": ["PF3D7_0523000"],
                        "wdkPrimaryKeyString": "PF3D7_0523000",
                    }
                ],
            },
            "organismCounts": {"Plasmodium falciparum 3D7": 100},
        }
        resp = SiteSearchResponse.model_validate(raw)
        assert resp.search_results.total_count == 42
        assert len(resp.search_results.documents) == 1
        assert (
            resp.search_results.documents[0].wdk_primary_key_string == "PF3D7_0523000"
        )
        assert resp.organism_counts["Plasmodium falciparum 3D7"] == 100

    def test_response_handles_empty(self) -> None:
        resp = SiteSearchResponse.model_validate({})
        assert resp.search_results.total_count == 0
        assert resp.search_results.documents == []
        assert resp.organism_counts == {}

    def test_response_new_fields_default_empty(self) -> None:
        """New fields (documentTypes, categories, fieldCounts) default to empty."""
        resp = SiteSearchResponse.model_validate({})
        assert resp.document_types == []
        assert resp.categories == []
        assert resp.field_counts == {}


class TestSiteSearchDocumentTypeField:
    """SiteSearchDocumentTypeField — aligned with SiteSearch/Types.ts."""

    def test_parses_from_live_shape(self) -> None:
        raw = {
            "name": "TEXT__gene_product",
            "displayName": "Product description",
            "term": "product",
            "isSubtitle": True,
        }
        field = SiteSearchDocumentTypeField.model_validate(raw)
        assert field.name == "TEXT__gene_product"
        assert field.display_name == "Product description"
        assert field.term == "product"
        assert field.is_subtitle is True

    def test_is_subtitle_defaults_false(self) -> None:
        raw = {"name": "TEXT__gene_name", "displayName": "Gene name", "term": "name"}
        field = SiteSearchDocumentTypeField.model_validate(raw)
        assert field.is_subtitle is False


class TestSiteSearchDocumentType:
    """SiteSearchDocumentType — aligned with SiteSearch/Types.ts discriminated union."""

    def test_parses_wdk_record_type_with_search_name(self) -> None:
        """WDK record types include wdkSearchName."""
        raw = {
            "id": "gene",
            "displayName": "Gene",
            "displayNamePlural": "Genes",
            "count": 721184,
            "hasOrganismField": True,
            "isWdkRecordType": True,
            "wdkSearchName": "GenesByText",
            "searchFields": [
                {
                    "name": "TEXT__gene_product",
                    "displayName": "Product description",
                    "term": "product",
                    "isSubtitle": True,
                },
            ],
            "summaryFields": [
                {
                    "name": "TEXT__gene_name",
                    "displayName": "Gene name or symbol",
                    "term": "name",
                    "isSubtitle": False,
                },
            ],
        }
        dt = SiteSearchDocumentType.model_validate(raw)
        assert dt.id == "gene"
        assert dt.display_name == "Gene"
        assert dt.display_name_plural == "Genes"
        assert dt.count == 721184
        assert dt.has_organism_field is True
        assert dt.is_wdk_record_type is True
        assert dt.wdk_search_name == "GenesByText"
        assert len(dt.search_fields) == 1
        assert dt.search_fields[0].term == "product"
        assert dt.search_fields[0].is_subtitle is True
        assert len(dt.summary_fields) == 1
        assert dt.summary_fields[0].term == "name"

    def test_parses_non_wdk_record_type(self) -> None:
        """Non-WDK types (news, general) have isWdkRecordType=false and no wdkSearchName."""
        raw = {
            "id": "news",
            "displayName": "News",
            "displayNamePlural": "News",
            "count": 0,
            "hasOrganismField": False,
            "isWdkRecordType": False,
            "searchFields": [
                {
                    "name": "TEXT__news_content",
                    "displayName": "Content",
                    "term": "content",
                    "isSubtitle": False,
                },
            ],
            "summaryFields": [],
        }
        dt = SiteSearchDocumentType.model_validate(raw)
        assert dt.id == "news"
        assert dt.is_wdk_record_type is False
        assert dt.wdk_search_name is None
        assert dt.has_organism_field is False
        assert len(dt.search_fields) == 1
        assert dt.summary_fields == []

    def test_defaults_for_minimal_input(self) -> None:
        raw = {"id": "test", "displayName": "Test", "displayNamePlural": "Tests"}
        dt = SiteSearchDocumentType.model_validate(raw)
        assert dt.count == 0
        assert dt.has_organism_field is False
        assert dt.is_wdk_record_type is False
        assert dt.wdk_search_name is None
        assert dt.search_fields == []
        assert dt.summary_fields == []


class TestSiteSearchCategory:
    """SiteSearchCategory — aligned with SiteSearch/Types.ts."""

    def test_parses_from_live_shape(self) -> None:
        raw = {"name": "Genome", "documentTypes": ["gene", "genomic-sequence"]}
        cat = SiteSearchCategory.model_validate(raw)
        assert cat.name == "Genome"
        assert cat.document_types == ["gene", "genomic-sequence"]

    def test_defaults_empty_document_types(self) -> None:
        cat = SiteSearchCategory.model_validate({"name": "Empty"})
        assert cat.document_types == []


class TestSiteSearchResponseFullAlignment:
    """SiteSearchResponse with all 5 top-level fields from WDK SiteSearchService."""

    def test_parses_full_live_response(self) -> None:
        """Parse a response shaped like the real PlasmoDB API."""
        raw = {
            "searchResults": {
                "totalCount": 721184,
                "documents": [
                    {
                        "documentType": "gene",
                        "primaryKey": ["PF3D7_0523000"],
                        "wdkPrimaryKeyString": "PF3D7_0523000",
                        "hyperlinkName": "protein kinase",
                        "organism": ["Plasmodium falciparum 3D7"],
                        "score": 43.7,
                        "summaryFieldData": {"TEXT__gene_product": "protein kinase"},
                        "foundInFields": {
                            "TEXT__gene_product": ["protein <em>kinase</em>"]
                        },
                    }
                ],
            },
            "organismCounts": {"Plasmodium falciparum 3D7": 100},
            "documentTypes": [
                {
                    "id": "gene",
                    "displayName": "Gene",
                    "displayNamePlural": "Genes",
                    "count": 721184,
                    "hasOrganismField": True,
                    "isWdkRecordType": True,
                    "wdkSearchName": "GenesByText",
                    "searchFields": [
                        {
                            "name": "TEXT__gene_product",
                            "displayName": "Product description",
                            "term": "product",
                            "isSubtitle": True,
                        },
                    ],
                    "summaryFields": [],
                },
                {
                    "id": "news",
                    "displayName": "News",
                    "displayNamePlural": "News",
                    "count": 0,
                    "hasOrganismField": False,
                    "isWdkRecordType": False,
                    "searchFields": [],
                    "summaryFields": [],
                },
            ],
            "categories": [
                {"name": "Genome", "documentTypes": ["gene", "genomic-sequence"]},
                {"name": "About", "documentTypes": ["news", "general"]},
            ],
            "fieldCounts": {
                "TEXT__gene_product": 135548,
                "MULTITEXT__gene_GOTerms": 202127,
            },
        }
        resp = SiteSearchResponse.model_validate(raw)

        # Existing fields still work.
        assert resp.search_results.total_count == 721184
        assert len(resp.search_results.documents) == 1
        assert resp.organism_counts["Plasmodium falciparum 3D7"] == 100

        # documentTypes
        assert len(resp.document_types) == 2
        gene_dt = resp.document_types[0]
        assert gene_dt.id == "gene"
        assert gene_dt.wdk_search_name == "GenesByText"
        assert gene_dt.is_wdk_record_type is True
        assert gene_dt.count == 721184
        news_dt = resp.document_types[1]
        assert news_dt.id == "news"
        assert news_dt.wdk_search_name is None
        assert news_dt.is_wdk_record_type is False

        # categories
        assert len(resp.categories) == 2
        assert resp.categories[0].name == "Genome"
        assert resp.categories[0].document_types == ["gene", "genomic-sequence"]

        # fieldCounts
        assert resp.field_counts["TEXT__gene_product"] == 135548
        assert resp.field_counts["MULTITEXT__gene_GOTerms"] == 202127

    def test_backward_compat_without_new_fields(self) -> None:
        """Old-style responses (only searchResults + organismCounts) still parse."""
        raw = {
            "searchResults": {"totalCount": 5, "documents": []},
            "organismCounts": {"Pf 3D7": 5},
        }
        resp = SiteSearchResponse.model_validate(raw)
        assert resp.search_results.total_count == 5
        assert resp.document_types == []
        assert resp.categories == []
        assert resp.field_counts == {}


# ---------------------------------------------------------------------------
# strip_html_tags
# ---------------------------------------------------------------------------


class TestStripHtmlTags:
    """site-search highlights matches with <em> tags; strip them."""

    def test_strips_em_tags(self) -> None:
        assert strip_html_tags("the <em>kinase</em> gene") == "the kinase gene"

    def test_strips_multiple_tags(self) -> None:
        assert strip_html_tags("<b>bold</b> and <i>italic</i>") == "bold and italic"

    def test_strips_self_closing_tags(self) -> None:
        assert strip_html_tags("line<br/>break") == "linebreak"

    def test_handles_empty_string(self) -> None:
        assert strip_html_tags("") == ""

    def test_handles_no_tags(self) -> None:
        assert strip_html_tags("plain text") == "plain text"

    def test_strips_and_trims_whitespace(self) -> None:
        assert strip_html_tags("  <em>test</em>  ") == "test"

    def test_handles_none_gracefully(self) -> None:
        # The function uses `value or ""` so None should not raise
        assert strip_html_tags(None) == ""


# ---------------------------------------------------------------------------
# SiteInfo.site_origin
# ---------------------------------------------------------------------------


class TestSiteOrigin:
    def test_strips_path_to_origin(self) -> None:
        site = SiteInfo(
            id="plasmodb",
            name="PlasmoDB",
            display_name="PlasmoDB",
            base_url="https://plasmodb.org/plasmo/service",
            project_id="PlasmoDB",
            is_portal=False,
        )
        assert site.site_origin == "https://plasmodb.org"

    def test_portal_origin(self) -> None:
        site = SiteInfo(
            id="veupathdb",
            name="VEuPathDB",
            display_name="VEuPathDB",
            base_url="https://veupathdb.org/veupathdb/service",
            project_id="EuPathDB",
            is_portal=True,
        )
        assert site.site_origin == "https://veupathdb.org"


# ---------------------------------------------------------------------------
# SiteSearchClient POST body construction (respx — internal mechanism)
# ---------------------------------------------------------------------------


class TestSiteSearchClientPostBody:
    """Verify POST body matches SearchRequest.java + SiteSearch/Types.ts contract.

    These tests use respx to verify the exact request body shape sent by
    SiteSearchClient. This is internal mechanism testing — the integration
    tests verify the end-to-end contract with real responses.
    """

    async def test_basic_search_body(self) -> None:
        captured_body: dict[str, object] = {}

        with respx.mock(assert_all_called=False) as router:

            def capture(request: httpx.Request) -> httpx.Response:
                captured_body.update(json.loads(request.content))
                return httpx.Response(200, json={})

            router.post("https://plasmodb.org/site-search").mock(side_effect=capture)
            client = SiteSearchClient("https://plasmodb.org", "PlasmoDB")
            try:
                await client.search("kinase")
            finally:
                await client.close()

        assert captured_body["searchText"] == "kinase"
        assert captured_body["restrictToProject"] == "PlasmoDB"
        assert captured_body["pagination"] == {"offset": 0, "numRecords": 20}

    async def test_with_document_type_filter(self) -> None:
        captured_body: dict[str, object] = {}

        with respx.mock(assert_all_called=False) as router:

            def capture(request: httpx.Request) -> httpx.Response:
                captured_body.update(json.loads(request.content))
                return httpx.Response(200, json={})

            router.post("https://plasmodb.org/site-search").mock(side_effect=capture)
            client = SiteSearchClient("https://plasmodb.org", "PlasmoDB")
            try:
                await client.search(
                    "kinase",
                    document_type_filter=DocumentTypeFilter(document_type="gene"),
                )
            finally:
                await client.close()

        assert captured_body["documentTypeFilter"] == {"documentType": "gene"}

    async def test_with_found_only_in_fields(self) -> None:
        captured_body: dict[str, object] = {}

        with respx.mock(assert_all_called=False) as router:

            def capture(request: httpx.Request) -> httpx.Response:
                captured_body.update(json.loads(request.content))
                return httpx.Response(200, json={})

            router.post("https://plasmodb.org/site-search").mock(side_effect=capture)
            client = SiteSearchClient("https://plasmodb.org", "PlasmoDB")
            try:
                await client.search(
                    "kinase",
                    document_type_filter=DocumentTypeFilter(
                        document_type="gene",
                        found_only_in_fields=["TEXT__gene_product"],
                    ),
                )
            finally:
                await client.close()

        assert captured_body["documentTypeFilter"] == {
            "documentType": "gene",
            "foundOnlyInFields": ["TEXT__gene_product"],
        }

    async def test_with_restrict_metadata_to_organisms(self) -> None:
        captured_body: dict[str, object] = {}

        with respx.mock(assert_all_called=False) as router:

            def capture(request: httpx.Request) -> httpx.Response:
                captured_body.update(json.loads(request.content))
                return httpx.Response(200, json={})

            router.post("https://plasmodb.org/site-search").mock(side_effect=capture)
            client = SiteSearchClient("https://plasmodb.org", "PlasmoDB")
            try:
                await client.search(
                    "kinase",
                    restrict_metadata_to_organisms=["Plasmodium falciparum 3D7"],
                )
            finally:
                await client.close()

        assert captured_body["restrictMetadataToOrganisms"] == [
            "Plasmodium falciparum 3D7"
        ]

    async def test_with_organisms_filter(self) -> None:
        captured_body: dict[str, object] = {}

        with respx.mock(assert_all_called=False) as router:

            def capture(request: httpx.Request) -> httpx.Response:
                captured_body.update(json.loads(request.content))
                return httpx.Response(200, json={})

            router.post("https://plasmodb.org/site-search").mock(side_effect=capture)
            client = SiteSearchClient("https://plasmodb.org", "PlasmoDB")
            try:
                await client.search("kinase", organisms=["Pf 3D7", "Pv P01"])
            finally:
                await client.close()

        assert captured_body["restrictSearchToOrganisms"] == ["Pf 3D7", "Pv P01"]

    async def test_custom_limit_and_offset(self) -> None:
        captured_body: dict[str, object] = {}

        with respx.mock(assert_all_called=False) as router:

            def capture(request: httpx.Request) -> httpx.Response:
                captured_body.update(json.loads(request.content))
                return httpx.Response(200, json={})

            router.post("https://plasmodb.org/site-search").mock(side_effect=capture)
            client = SiteSearchClient("https://plasmodb.org", "PlasmoDB")
            try:
                await client.search("kinase", limit=50, offset=10)
            finally:
                await client.close()

        assert captured_body["pagination"] == {"offset": 10, "numRecords": 50}

    async def test_default_search_text_star(self) -> None:
        captured_body: dict[str, object] = {}

        with respx.mock(assert_all_called=False) as router:

            def capture(request: httpx.Request) -> httpx.Response:
                captured_body.update(json.loads(request.content))
                return httpx.Response(200, json={})

            router.post("https://plasmodb.org/site-search").mock(side_effect=capture)
            client = SiteSearchClient("https://plasmodb.org", "PlasmoDB")
            try:
                await client.search("")
            finally:
                await client.close()

        assert captured_body["searchText"] == "*"


# ---------------------------------------------------------------------------
# SiteSearchClient retry/error (respx — controlled failure injection)
# ---------------------------------------------------------------------------


class TestSiteSearchClientRetry:
    async def test_retries_on_timeout(self) -> None:
        call_count = 0

        with respx.mock(assert_all_called=False) as router:

            def handler(request: httpx.Request) -> httpx.Response:
                nonlocal call_count
                call_count += 1
                if call_count < 3:
                    msg = "timeout"
                    raise httpx.ReadTimeout(msg, request=request)
                return httpx.Response(200, json={})

            router.post("https://plasmodb.org/site-search").mock(side_effect=handler)
            client = SiteSearchClient("https://plasmodb.org", "PlasmoDB")
            try:
                resp = await client.search("kinase")
            finally:
                await client.close()
            assert call_count == 3
            assert isinstance(resp, SiteSearchResponse)

    async def test_retries_on_connect_error(self) -> None:
        call_count = 0

        with respx.mock(assert_all_called=False) as router:

            def handler(request: httpx.Request) -> httpx.Response:
                nonlocal call_count
                call_count += 1
                if call_count < 2:
                    msg = "connection refused"
                    raise httpx.ConnectError(msg, request=request)
                return httpx.Response(200, json={})

            router.post("https://plasmodb.org/site-search").mock(side_effect=handler)
            client = SiteSearchClient("https://plasmodb.org", "PlasmoDB")
            try:
                await client.search("kinase")
            finally:
                await client.close()
            assert call_count == 2

    async def test_no_retry_on_client_error(self) -> None:
        """HTTP 400 should raise immediately, not retry."""
        with respx.mock(assert_all_called=False) as router:
            route = router.post("https://plasmodb.org/site-search").respond(400)
            client = SiteSearchClient("https://plasmodb.org", "PlasmoDB")
            try:
                with pytest.raises(AppError):
                    await client.search("kinase")
            finally:
                await client.close()
            assert route.call_count == 1

    async def test_raises_app_error_after_max_retries(self) -> None:
        with respx.mock(assert_all_called=False) as router:

            def handler(request: httpx.Request) -> httpx.Response:
                msg = "timeout"
                raise httpx.ReadTimeout(msg, request=request)

            router.post("https://plasmodb.org/site-search").mock(side_effect=handler)
            client = SiteSearchClient("https://plasmodb.org", "PlasmoDB")
            try:
                with pytest.raises(AppError):
                    await client.search("kinase")
            finally:
                await client.close()


class TestSiteSearchClientErrorHandling:
    async def test_wraps_http_error_into_app_error(self) -> None:
        with respx.mock(assert_all_called=False) as router:
            router.post("https://plasmodb.org/site-search").respond(500)
            client = SiteSearchClient("https://plasmodb.org", "PlasmoDB")
            try:
                with pytest.raises(AppError):
                    await client.search("kinase")
            finally:
                await client.close()


class TestSiteSearchClientLifecycle:
    async def test_close_closes_httpx_client(self) -> None:
        client = SiteSearchClient("https://plasmodb.org", "PlasmoDB")
        with respx.mock(assert_all_called=False) as router:
            router.post("https://plasmodb.org/site-search").respond(json={})
            await client.search("kinase")
        assert client._client is not None
        await client.close()
        assert client._client is None

    async def test_close_idempotent(self) -> None:
        client = SiteSearchClient("https://plasmodb.org", "PlasmoDB")
        await client.close()
        await client.close()  # should not raise


# ---------------------------------------------------------------------------
# SiteRouter.get_site_search_client
# ---------------------------------------------------------------------------


class TestSiteRouterSiteSearchClient:
    def test_get_site_search_client_returns_client(self) -> None:
        with patch(
            "veupath_chatbot.integrations.veupathdb.site_router.get_settings",
            return_value=MagicMock(
                veupathdb_sites_config=None,
                veupathdb_auth_token=None,
                veupathdb_default_site="veupathdb",
            ),
        ):
            router = SiteRouter()
            client = router.get_site_search_client("plasmodb")
            assert isinstance(client, SiteSearchClient)

    def test_get_site_search_client_cached(self) -> None:
        with patch(
            "veupath_chatbot.integrations.veupathdb.site_router.get_settings",
            return_value=MagicMock(
                veupathdb_sites_config=None,
                veupathdb_auth_token=None,
                veupathdb_default_site="veupathdb",
            ),
        ):
            router = SiteRouter()
            c1 = router.get_site_search_client("plasmodb")
            c2 = router.get_site_search_client("plasmodb")
            assert c1 is c2

    def test_get_site_search_client_correct_origin(self) -> None:
        with patch(
            "veupath_chatbot.integrations.veupathdb.site_router.get_settings",
            return_value=MagicMock(
                veupathdb_sites_config=None,
                veupathdb_auth_token=None,
                veupathdb_default_site="veupathdb",
            ),
        ):
            router = SiteRouter()
            client = router.get_site_search_client("plasmodb")
            # Origin should be https://plasmodb.org, NOT https://plasmodb.org/plasmo/service
            assert client._base_url == "https://plasmodb.org"

    def test_get_site_search_client_correct_project_id(self) -> None:
        with patch(
            "veupath_chatbot.integrations.veupathdb.site_router.get_settings",
            return_value=MagicMock(
                veupathdb_sites_config=None,
                veupathdb_auth_token=None,
                veupathdb_default_site="veupathdb",
            ),
        ):
            router = SiteRouter()
            client = router.get_site_search_client("plasmodb")
            assert client._project_id == "PlasmoDB"

    async def test_close_all_closes_site_search_clients(self) -> None:
        with patch(
            "veupath_chatbot.integrations.veupathdb.site_router.get_settings",
            return_value=MagicMock(
                veupathdb_sites_config=None,
                veupathdb_auth_token=None,
                veupathdb_default_site="veupathdb",
            ),
        ):
            router = SiteRouter()
            client = router.get_site_search_client("plasmodb")
            await router.close_all()
            # After close_all, the client should be cleaned up
            assert client._client is None
