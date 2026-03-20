"""Unit tests for veupath_chatbot.integrations.veupathdb.site_search.

Tests query_site_search payload construction, URL derivation from site config,
and the strip_html_tags helper. Uses respx to mock outbound HTTP.
"""

from unittest.mock import MagicMock, patch

import httpx
import respx

import veupath_chatbot.integrations.veupathdb.site_search as mod
from veupath_chatbot.integrations.veupathdb.site_router import SiteInfo
from veupath_chatbot.integrations.veupathdb.site_search import (
    query_site_search,
    strip_html_tags,
)

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
# query_site_search
# ---------------------------------------------------------------------------


def _mock_site(
    base_url: str = "https://plasmodb.org/plasmo/service",
    project_id: str = "PlasmoDB",
) -> SiteInfo:
    return SiteInfo(
        site_id="plasmodb",
        name="PlasmoDB",
        display_name="PlasmoDB",
        base_url=base_url,
        project_id=project_id,
        is_portal=False,
    )


def _mock_router(site: SiteInfo | None = None) -> MagicMock:
    router = MagicMock()
    router.get_site.return_value = site or _mock_site()
    return router


class TestQuerySiteSearchUrlDerivation:
    """URL is derived from site origin, not the WDK service path."""

    async def test_url_is_site_origin_plus_site_search(self) -> None:
        """site-search is at https://plasmodb.org/site-search, not under /plasmo/service."""
        mock_router = _mock_router()
        response_data = {"searchResults": [], "totalCount": 0}

        with (
            patch(
                "veupath_chatbot.integrations.veupathdb.site_search.get_site_router",
                return_value=mock_router,
            ),
            respx.mock(assert_all_called=False) as router,
        ):
            route = router.get("https://plasmodb.org/site-search").respond(
                json=response_data
            )
            # Reset the global client to ensure respx intercepts
            mod._site_search_client = None

            result = await query_site_search("plasmodb", search_text="kinase")

        assert route.called
        assert result == response_data


class TestQuerySiteSearchParams:
    """Verify the request params match the site-search GET API contract.

    The VEuPathDB site-search endpoint is GET-only (POST returns HTTP 500).
    Parameters are passed as query-string key-value pairs.
    """

    async def test_basic_search_params(self) -> None:
        mock_router = _mock_router()
        captured_params: dict[str, str] = {}

        with (
            patch(
                "veupath_chatbot.integrations.veupathdb.site_search.get_site_router",
                return_value=mock_router,
            ),
            respx.mock(assert_all_called=False) as router,
        ):

            def capture_request(request: httpx.Request) -> httpx.Response:
                captured_params.update(dict(request.url.params.items()))
                return httpx.Response(200, json={"searchResults": []})

            router.get("https://plasmodb.org/site-search").mock(
                side_effect=capture_request
            )
            mod._site_search_client = None

            await query_site_search("plasmodb", search_text="kinase")

        assert captured_params["searchText"] == "kinase"
        assert captured_params["restrictToProject"] == "PlasmoDB"
        assert captured_params["offset"] == "0"
        assert captured_params["numRecords"] == "20"

    async def test_with_document_type_filter(self) -> None:
        mock_router = _mock_router()
        captured_params: dict[str, str] = {}

        with (
            patch(
                "veupath_chatbot.integrations.veupathdb.site_search.get_site_router",
                return_value=mock_router,
            ),
            respx.mock(assert_all_called=False) as router,
        ):

            def capture_request(request: httpx.Request) -> httpx.Response:
                captured_params.update(dict(request.url.params.items()))
                return httpx.Response(200, json={})

            router.get("https://plasmodb.org/site-search").mock(
                side_effect=capture_request
            )
            mod._site_search_client = None

            await query_site_search(
                "plasmodb", search_text="kinase", document_type="gene"
            )

        assert captured_params["docType"] == "gene"

    async def test_with_organisms_filter(self) -> None:
        mock_router = _mock_router()
        captured_params: dict[str, str] = {}

        with (
            patch(
                "veupath_chatbot.integrations.veupathdb.site_search.get_site_router",
                return_value=mock_router,
            ),
            respx.mock(assert_all_called=False) as router,
        ):

            def capture_request(request: httpx.Request) -> httpx.Response:
                captured_params.update(dict(request.url.params.items()))
                return httpx.Response(200, json={})

            router.get("https://plasmodb.org/site-search").mock(
                side_effect=capture_request
            )
            mod._site_search_client = None

            await query_site_search(
                "plasmodb",
                search_text="test",
                organisms=["Plasmodium falciparum 3D7"],
            )

        assert captured_params["restrictSearchToOrganisms"] == (
            "Plasmodium falciparum 3D7"
        )

    async def test_multiple_organisms_joined_by_comma(self) -> None:
        mock_router = _mock_router()
        captured_params: dict[str, str] = {}

        with (
            patch(
                "veupath_chatbot.integrations.veupathdb.site_search.get_site_router",
                return_value=mock_router,
            ),
            respx.mock(assert_all_called=False) as router,
        ):

            def capture_request(request: httpx.Request) -> httpx.Response:
                captured_params.update(dict(request.url.params.items()))
                return httpx.Response(200, json={})

            router.get("https://plasmodb.org/site-search").mock(
                side_effect=capture_request
            )
            mod._site_search_client = None

            await query_site_search(
                "plasmodb",
                search_text="test",
                organisms=[
                    "Plasmodium falciparum 3D7",
                    "Plasmodium vivax P01",
                ],
            )

        assert captured_params["restrictSearchToOrganisms"] == (
            "Plasmodium falciparum 3D7,Plasmodium vivax P01"
        )

    async def test_custom_limit_and_offset(self) -> None:
        mock_router = _mock_router()
        captured_params: dict[str, str] = {}

        with (
            patch(
                "veupath_chatbot.integrations.veupathdb.site_search.get_site_router",
                return_value=mock_router,
            ),
            respx.mock(assert_all_called=False) as router,
        ):

            def capture_request(request: httpx.Request) -> httpx.Response:
                captured_params.update(dict(request.url.params.items()))
                return httpx.Response(200, json={})

            router.get("https://plasmodb.org/site-search").mock(
                side_effect=capture_request
            )
            mod._site_search_client = None

            await query_site_search("plasmodb", search_text="test", limit=50, offset=10)

        assert captured_params["offset"] == "10"
        assert captured_params["numRecords"] == "50"

    async def test_empty_response_returns_empty_dict(self) -> None:
        mock_router = _mock_router()

        with (
            patch(
                "veupath_chatbot.integrations.veupathdb.site_search.get_site_router",
                return_value=mock_router,
            ),
            respx.mock(assert_all_called=False) as router,
        ):
            # Empty content body
            router.get("https://plasmodb.org/site-search").respond(200, content=b"")
            mod._site_search_client = None

            result = await query_site_search("plasmodb", search_text="test")

        assert result == {}
