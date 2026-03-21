"""Unit tests for veupath_chatbot.integrations.veupathdb.site_search_client.

Tests SiteSearchClient payload construction, response parsing, retry logic,
and SiteRouter.get_site_search_client integration.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import respx

from veupath_chatbot.integrations.veupathdb.site_router import SiteInfo, SiteRouter
from veupath_chatbot.integrations.veupathdb.site_search_client import (
    SiteSearchClient,
    SiteSearchDocument,
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
        assert resp.search_results.documents[0].wdk_primary_key_string == "PF3D7_0523000"
        assert resp.organism_counts["Plasmodium falciparum 3D7"] == 100

    def test_response_handles_empty(self) -> None:
        resp = SiteSearchResponse.model_validate({})
        assert resp.search_results.total_count == 0
        assert resp.search_results.documents == []
        assert resp.organism_counts == {}

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
# SiteSearchClient
# ---------------------------------------------------------------------------


class TestSiteSearchClientPostBody:
    """Verify POST body matches SearchRequest.java + SiteSearch/Types.ts contract."""

    async def test_url_is_site_origin_plus_site_search(self) -> None:
        with respx.mock(assert_all_called=False) as router:
            route = router.post("https://plasmodb.org/site-search").respond(json={})
            client = SiteSearchClient("https://plasmodb.org", "PlasmoDB")
            try:
                await client.search("kinase")
            finally:
                await client.close()
            assert route.called

    async def test_uses_post_not_get(self) -> None:
        with respx.mock(assert_all_called=False) as router:
            router.post("https://plasmodb.org/site-search").respond(json={})
            get_route = router.get("https://plasmodb.org/site-search").respond(json={})
            client = SiteSearchClient("https://plasmodb.org", "PlasmoDB")
            try:
                await client.search("kinase")
            finally:
                await client.close()
            assert not get_route.called

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
                await client.search("kinase", document_type="gene")
            finally:
                await client.close()

        assert captured_body["documentTypeFilter"] == {"documentType": "gene"}

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


class TestSiteSearchClientResponseParsing:
    async def test_returns_typed_response(self) -> None:
        with respx.mock(assert_all_called=False) as router:
            router.post("https://plasmodb.org/site-search").respond(
                json={"searchResults": {"totalCount": 5, "documents": []}}
            )
            client = SiteSearchClient("https://plasmodb.org", "PlasmoDB")
            try:
                resp = await client.search("kinase")
            finally:
                await client.close()
            assert isinstance(resp, SiteSearchResponse)
            assert resp.search_results.total_count == 5

    async def test_parses_documents(self) -> None:
        with respx.mock(assert_all_called=False) as router:
            router.post("https://plasmodb.org/site-search").respond(json={
                "searchResults": {
                    "totalCount": 1,
                    "documents": [{"documentType": "gene", "primaryKey": ["PF3D7_0523000"]}],
                },
            })
            client = SiteSearchClient("https://plasmodb.org", "PlasmoDB")
            try:
                resp = await client.search("kinase")
            finally:
                await client.close()
            assert len(resp.search_results.documents) == 1
            assert resp.search_results.documents[0].primary_key == ["PF3D7_0523000"]

    async def test_parses_organism_counts(self) -> None:
        with respx.mock(assert_all_called=False) as router:
            router.post("https://plasmodb.org/site-search").respond(json={
                "organismCounts": {"Plasmodium falciparum 3D7": 100, "Toxoplasma gondii": 50},
            })
            client = SiteSearchClient("https://plasmodb.org", "PlasmoDB")
            try:
                resp = await client.search("kinase")
            finally:
                await client.close()
            assert resp.organism_counts == {"Plasmodium falciparum 3D7": 100, "Toxoplasma gondii": 50}

    async def test_parses_total_count(self) -> None:
        with respx.mock(assert_all_called=False) as router:
            router.post("https://plasmodb.org/site-search").respond(json={
                "searchResults": {"totalCount": 42, "documents": []},
            })
            client = SiteSearchClient("https://plasmodb.org", "PlasmoDB")
            try:
                resp = await client.search("kinase")
            finally:
                await client.close()
            assert resp.search_results.total_count == 42

    async def test_empty_body_returns_default(self) -> None:
        with respx.mock(assert_all_called=False) as router:
            router.post("https://plasmodb.org/site-search").respond(200, content=b"")
            client = SiteSearchClient("https://plasmodb.org", "PlasmoDB")
            try:
                resp = await client.search("kinase")
            finally:
                await client.close()
            assert resp.search_results.total_count == 0
            assert resp.search_results.documents == []


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
            with patch.object(client, "close", new_callable=AsyncMock) as mock_close:
                await router.close_all()
                mock_close.assert_called_once()
