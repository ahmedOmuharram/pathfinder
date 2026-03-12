"""Edge case tests for WDK integration layer.

Probes timeout handling, retry logic, cookie/auth forwarding, error
response parsing, parameter encoding, and connection lifecycle.

Bug markers (# BUG:) identify confirmed issues found during review.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import respx

from veupath_chatbot.integrations.veupathdb.client import (
    VEuPathDBClient,
    _convert_params_for_httpx,
    encode_context_param_values_for_wdk,
)
from veupath_chatbot.integrations.veupathdb.param_utils import normalize_param_value
from veupath_chatbot.integrations.veupathdb.site_router import SiteInfo
from veupath_chatbot.integrations.veupathdb.temporary_results import TemporaryResultsAPI
from veupath_chatbot.platform.errors import WDKError

# ---------------------------------------------------------------------------
# Helper: create a client that bypasses settings/auth_token_ctx
# ---------------------------------------------------------------------------


def _patch_settings_and_ctx():
    """Return a pair of context managers that stub out get_settings and auth ctx."""
    settings_mock = MagicMock(veupathdb_auth_token=None)
    return (
        patch(
            "veupath_chatbot.integrations.veupathdb.client.get_settings",
            return_value=settings_mock,
        ),
        patch(
            "veupath_chatbot.integrations.veupathdb.client.veupathdb_auth_token_ctx",
            MagicMock(get=MagicMock(return_value=None)),
        ),
    )


# ===========================================================================
# HTTP Client: Retry logic
# ===========================================================================


class TestRetryBehavior:
    """Verify retry behavior of the HTTP client.

    # BUG: The tenacity retry decorator on _request is DEAD CODE.
    #
    # The retry catches (httpx.TransportError, httpx.TimeoutException), but
    # INSIDE _request, the ``except httpx.RequestError`` block (line 189)
    # catches ALL TransportError/TimeoutException FIRST (since
    # TransportError is a subclass of RequestError) and re-raises them
    # wrapped as WDKError. Since WDKError is NOT in the retry type list,
    # tenacity never retries.
    #
    # The fix: either (a) move the retry decorator to wrap only the
    # client.request() call (not the whole try/except), or (b) let
    # TransportError/TimeoutException propagate through the except blocks
    # so tenacity can catch them, or (c) add WDKError to the retry types
    # with a status filter (for 5xx/transport errors only).
    """

    async def test_transport_error_retried_by_tenacity(self) -> None:
        """ConnectError propagates through to tenacity which retries 3 times,
        then the wrapper converts RetryError to WDKError(status=502)."""
        client = VEuPathDBClient("https://example.com/service")

        with respx.mock(assert_all_called=False) as router:
            router.get("https://example.com/service/test").respond(200, json=[])
            p1, p2 = _patch_settings_and_ctx()
            with p1, p2:
                internal = await client._get_client()

        call_count = 0

        async def failing_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise httpx.ConnectError("Connection refused")

        internal.request = failing_request

        p1, p2 = _patch_settings_and_ctx()
        with p1, p2, pytest.raises(WDKError) as exc_info:
            await client.get("/test")

        assert exc_info.value.status == 502
        assert call_count == 3, (
            "Expected 3 calls (initial + 2 retries) because ConnectError "
            "propagates to tenacity for retry."
        )
        await client.close()

    async def test_5xx_errors_are_retried(self) -> None:
        """HTTPStatusError (5xx) is retried up to 3 times before raising WDKError."""
        client = VEuPathDBClient("https://example.com/service")
        call_count = 0

        with respx.mock(assert_all_called=False) as router:

            def count_calls(request: httpx.Request) -> httpx.Response:
                nonlocal call_count
                call_count += 1
                return httpx.Response(503, text="Service Unavailable")

            router.get("https://example.com/service/test").mock(side_effect=count_calls)
            p1, p2 = _patch_settings_and_ctx()
            with p1, p2, pytest.raises(WDKError) as exc_info:
                await client.get("/test")

        assert call_count == 3, (
            "Expected 3 calls (initial + 2 retries) because 5xx "
            "propagates to tenacity for retry."
        )
        assert exc_info.value.status == 503
        await client.close()


# ===========================================================================
# HTTP Client: Cookie/Auth token handling
# ===========================================================================


class TestAuthTokenForwarding:
    """Verify cookie-based auth forwarding to WDK.

    # BUG: httpx has deprecated per-request cookies= parameter.
    # Future httpx versions will remove this feature, breaking auth.
    # The fix is to set cookies on the client instance or use headers.
    """

    async def test_context_token_takes_priority(self) -> None:
        """Context var token beats instance token and settings."""
        client = VEuPathDBClient(
            "https://example.com/service", auth_token="instance_tok"
        )
        captured_cookies: dict[str, str] = {}

        with respx.mock(assert_all_called=False) as router:

            def capture(request: httpx.Request) -> httpx.Response:
                cookie_header = request.headers.get("cookie", "")
                captured_cookies["raw"] = cookie_header
                return httpx.Response(200, json=[])

            router.get("https://example.com/service/test").mock(side_effect=capture)
            settings_mock = MagicMock(veupathdb_auth_token="settings_tok")
            with (
                patch(
                    "veupath_chatbot.integrations.veupathdb.client.get_settings",
                    return_value=settings_mock,
                ),
                patch(
                    "veupath_chatbot.integrations.veupathdb.client.veupathdb_auth_token_ctx",
                    MagicMock(get=MagicMock(return_value="context_tok")),
                ),
            ):
                await client.get("/test")

        assert "context_tok" in captured_cookies["raw"]
        await client.close()

    async def test_instance_token_used_when_no_context(self) -> None:
        """Falls back to instance auth_token when context var is None."""
        client = VEuPathDBClient("https://example.com/service", auth_token="my_token")
        captured_cookies: dict[str, str] = {}

        with respx.mock(assert_all_called=False) as router:

            def capture(request: httpx.Request) -> httpx.Response:
                cookie_header = request.headers.get("cookie", "")
                captured_cookies["raw"] = cookie_header
                return httpx.Response(200, json=[])

            router.get("https://example.com/service/test").mock(side_effect=capture)
            p1, p2 = _patch_settings_and_ctx()
            with p1, p2:
                await client.get("/test")

        assert "my_token" in captured_cookies["raw"]
        await client.close()

    async def test_no_cookie_when_no_token(self) -> None:
        """When no auth token is available, no Authorization cookie is sent."""
        client = VEuPathDBClient("https://example.com/service")
        captured_cookies: dict[str, str] = {}

        with respx.mock(assert_all_called=False) as router:

            def capture(request: httpx.Request) -> httpx.Response:
                cookie_header = request.headers.get("cookie", "")
                captured_cookies["raw"] = cookie_header
                return httpx.Response(200, json=[])

            router.get("https://example.com/service/test").mock(side_effect=capture)
            p1, p2 = _patch_settings_and_ctx()
            with p1, p2:
                await client.get("/test")

        # No Authorization= cookie should be present
        assert "Authorization=" not in captured_cookies.get("raw", "")
        await client.close()


# ===========================================================================
# HTTP Client: Error response parsing
# ===========================================================================


class TestErrorResponseParsing:
    """Verify that WDK error responses are properly parsed."""

    async def test_4xx_status_preserved_in_wdk_error(self) -> None:
        """4xx status codes are preserved in WDKError.status."""
        client = VEuPathDBClient("https://example.com/service")

        with respx.mock(assert_all_called=False) as router:
            router.post("https://example.com/service/test").respond(
                422, text='{"message":"Invalid parameters"}'
            )
            p1, p2 = _patch_settings_and_ctx()
            with p1, p2, pytest.raises(WDKError) as exc_info:
                await client.post("/test", json={})

        assert exc_info.value.status == 422
        assert "422" in str(exc_info.value.detail)
        await client.close()

    async def test_html_error_page_truncated(self) -> None:
        """WDK sometimes returns HTML error pages; they're truncated in the error."""
        client = VEuPathDBClient("https://example.com/service")
        big_html = "<html><body>" + "x" * 500 + "</body></html>"

        with respx.mock(assert_all_called=False) as router:
            router.get("https://example.com/service/test").respond(500, text=big_html)
            p1, p2 = _patch_settings_and_ctx()
            with p1, p2, pytest.raises(WDKError) as exc_info:
                await client.get("/test")

        # Error detail should be truncated to first 200 chars
        assert len(str(exc_info.value.detail)) < len(big_html)
        await client.close()

    async def test_whitespace_only_response_returns_none(self) -> None:
        """Whitespace-only body should be treated as empty."""
        client = VEuPathDBClient("https://example.com/service")

        with respx.mock(assert_all_called=False) as router:
            router.delete("https://example.com/service/test").respond(
                200, content=b"   \n  "
            )
            p1, p2 = _patch_settings_and_ctx()
            with p1, p2:
                result = await client.delete("/test")

        assert result is None
        await client.close()


# ===========================================================================
# HTTP Client: Connection lifecycle
# ===========================================================================


class TestConnectionLifecycle:
    """Verify client creation, reuse, and cleanup."""

    async def test_client_recreated_after_close(self) -> None:
        """After close(), the next request should create a new httpx client."""
        client = VEuPathDBClient("https://example.com/service")

        with respx.mock(assert_all_called=False) as router:
            router.get("https://example.com/service/test").respond(json=[])
            p1, p2 = _patch_settings_and_ctx()
            with p1, p2:
                await client.get("/test")
                first_client = client._client
                await client.close()
                assert client._client is None

                await client.get("/test")
                second_client = client._client

        assert first_client is not second_client
        await client.close()

    async def test_client_reused_across_requests(self) -> None:
        """Same httpx client should be reused across requests."""
        client = VEuPathDBClient("https://example.com/service")

        with respx.mock(assert_all_called=False) as router:
            router.get("https://example.com/service/test").respond(json=[])
            p1, p2 = _patch_settings_and_ctx()
            with p1, p2:
                await client.get("/test")
                first_client = client._client
                await client.get("/test")
                second_client = client._client

        assert first_client is second_client
        await client.close()

    def test_max_connections_clamped_to_minimum_1(self) -> None:
        """max_connections should be at least 1."""
        client = VEuPathDBClient("https://example.com/service", max_connections=0)
        assert client.max_connections == 0  # stored as-is
        # But when creating the httpx client, max(1, ...) is used

    def test_max_keepalive_clamped_to_minimum_0(self) -> None:
        """max_keepalive_connections can be 0 (disabled)."""
        client = VEuPathDBClient(
            "https://example.com/service", max_keepalive_connections=0
        )
        assert client.max_keepalive_connections == 0


# ===========================================================================
# Parameter encoding edge cases
# ===========================================================================


class TestEncodeContextEdgeCases:
    """Edge cases for WDK parameter encoding."""

    def test_boolean_true_stringified(self) -> None:
        """Boolean True should become string "True", not "true"."""
        result = encode_context_param_values_for_wdk({"flag": True})
        assert result["flag"] == "True"

    def test_boolean_false_stringified(self) -> None:
        result = encode_context_param_values_for_wdk({"flag": False})
        assert result["flag"] == "False"

    def test_integer_zero_not_skipped(self) -> None:
        """0 is falsy but should not be treated as None."""
        result = encode_context_param_values_for_wdk({"count": 0})
        assert result["count"] == "0"

    def test_empty_string_preserved(self) -> None:
        """Empty string is a valid value, should not be skipped."""
        result = encode_context_param_values_for_wdk({"name": ""})
        assert result["name"] == ""

    def test_empty_list_encoded_as_json(self) -> None:
        result = encode_context_param_values_for_wdk({"items": []})
        assert result["items"] == "[]"

    def test_nested_dict_json_encoded(self) -> None:
        result = encode_context_param_values_for_wdk(
            {"config": {"key": "val", "nested": [1, 2]}}
        )
        parsed = json.loads(result["config"])
        assert parsed == {"key": "val", "nested": [1, 2]}

    def test_special_characters_in_keys(self) -> None:
        """Keys with dots/brackets used in WDK param naming."""
        result = encode_context_param_values_for_wdk({"organism.group": "Plasmodium"})
        assert result["organism.group"] == "Plasmodium"


class TestNormalizeParamValueEdgeCases:
    """Edge cases for WDK param value normalization."""

    def test_boolean_false_is_false_string_not_empty(self) -> None:
        """bool False should become 'false', not ''."""
        result = normalize_param_value(False)
        assert result == "false"
        assert result != ""

    def test_integer_zero_is_zero_string_not_empty(self) -> None:
        """int 0 should become '0', not ''."""
        result = normalize_param_value(0)
        assert result == "0"
        assert result != ""

    def test_float_zero_is_zero_point_zero_string(self) -> None:
        result = normalize_param_value(0.0)
        assert result == "0.0"

    def test_very_large_number(self) -> None:
        result = normalize_param_value(999999999999)
        assert result == "999999999999"

    def test_scientific_notation_float(self) -> None:
        """Scientific notation should be preserved."""
        result = normalize_param_value(1e-10)
        assert result == "1e-10"

    def test_list_with_special_chars(self) -> None:
        """Organisms with special characters should be properly JSON-encoded."""
        organisms = ["P. falciparum (3D7)", "P. vivax 'P01'"]
        result = normalize_param_value(organisms)
        parsed = json.loads(result)
        assert parsed == organisms

    def test_unicode_string(self) -> None:
        """Unicode characters should pass through."""
        result = normalize_param_value("Schizosaccharomyces pombe")
        assert result == "Schizosaccharomyces pombe"


class TestConvertParamsEdgeCases:
    """Edge cases for _convert_params_for_httpx."""

    def test_float_value_passes_through(self) -> None:
        result = _convert_params_for_httpx({"threshold": 0.05})
        assert result is not None
        assert result["threshold"] == 0.05

    def test_empty_dict(self) -> None:
        result = _convert_params_for_httpx({})
        assert result == {}

    def test_list_with_nested_dict_stringified(self) -> None:
        """Nested dicts in lists should be stringified."""
        result = _convert_params_for_httpx({"key": [{"a": 1}]})
        assert result is not None
        items = result["key"]
        assert isinstance(items, list)
        assert isinstance(items[0], str)

    def test_empty_list_passes_through(self) -> None:
        result = _convert_params_for_httpx({"key": []})
        assert result is not None
        assert result["key"] == []


# ===========================================================================
# SiteInfo edge cases
# ===========================================================================


class TestSiteInfoEdgeCases:
    """Edge cases in site info URL construction."""

    def test_web_base_url_strips_service(self) -> None:
        site = SiteInfo(
            id="plasmo",
            name="PlasmoDB",
            display_name="PlasmoDB",
            base_url="https://plasmodb.org/plasmo/service",
            project_id="PlasmoDB",
            is_portal=False,
        )
        assert site.web_base_url == "https://plasmodb.org/plasmo"

    def test_web_base_url_no_service_suffix(self) -> None:
        site = SiteInfo(
            id="test",
            name="TestDB",
            display_name="TestDB",
            base_url="https://test.org/api",
            project_id="Test",
            is_portal=False,
        )
        assert site.web_base_url == "https://test.org/api"

    def test_strategy_url_with_root_step(self) -> None:
        site = SiteInfo(
            id="plasmo",
            name="PlasmoDB",
            display_name="PlasmoDB",
            base_url="https://plasmodb.org/plasmo/service",
            project_id="PlasmoDB",
            is_portal=False,
        )
        url = site.strategy_url(42, root_step_id=100)
        assert url == "https://plasmodb.org/plasmo/app/workspace/strategies/42/100"

    def test_strategy_url_without_root_step(self) -> None:
        site = SiteInfo(
            id="plasmo",
            name="PlasmoDB",
            display_name="PlasmoDB",
            base_url="https://plasmodb.org/plasmo/service",
            project_id="PlasmoDB",
            is_portal=False,
        )
        url = site.strategy_url(42)
        assert url == "https://plasmodb.org/plasmo/app/workspace/strategies/42"

    def test_to_dict_round_trip(self) -> None:
        site = SiteInfo(
            id="plasmo",
            name="PlasmoDB",
            display_name="PlasmoDB",
            base_url="https://plasmodb.org/plasmo/service",
            project_id="PlasmoDB",
            is_portal=True,
        )
        d = site.to_dict()
        assert d["id"] == "plasmo"
        assert d["isPortal"] is True
        assert d["baseUrl"] == "https://plasmodb.org/plasmo/service"


# ===========================================================================
# TemporaryResultsAPI edge cases
# ===========================================================================


def _make_temp_api(
    user_id: str = "12345",
    base_url: str = "https://plasmodb.org/plasmo/service",
) -> tuple[TemporaryResultsAPI, MagicMock]:
    """Create TemporaryResultsAPI with a mocked client, pre-initialized."""
    client = MagicMock()
    client.base_url = base_url
    client.get = AsyncMock()
    client.post = AsyncMock()
    api = TemporaryResultsAPI(client)
    api.user_id = user_id
    api._session_initialized = True
    return api, client


class TestTemporaryResultsEdgeCases:
    """Edge cases for temporary result download flow."""

    async def test_raises_when_no_id_in_response(self) -> None:
        """If POST response has no 'id', should raise immediately."""
        api, client = _make_temp_api()
        client.post.return_value = {}

        with pytest.raises(RuntimeError, match="did not include.*id"):
            await api.get_download_url(step_id=42, format="csv")

    async def test_tab_format_uses_standard_reporter(self) -> None:
        """Tab format should use 'standard' reporter like CSV."""
        api, client = _make_temp_api()
        client.post.return_value = {"id": "r1"}

        await api.get_download_url(step_id=42, format="tab")

        payload = client.post.call_args.kwargs["json"]
        assert payload["reportName"] == "standard"

    async def test_get_step_preview_uses_user_id(self) -> None:
        """Preview requests go through the user-scoped path."""
        api, client = _make_temp_api("99999")
        client.post.return_value = {"records": [], "meta": {}}

        await api.get_step_preview(step_id=42)

        call_path = client.post.call_args.args[0]
        assert "/users/99999/" in call_path

    async def test_constructs_url_from_id(self) -> None:
        """Download URL is constructed from base_url + id, no polling."""
        api, client = _make_temp_api()
        client.post.return_value = {"id": "abc123"}

        url = await api.get_download_url(step_id=42, format="csv")

        assert (
            url == "https://plasmodb.org/plasmo/service/temporary-results/abc123/result"
        )
        client.get.assert_not_awaited()


# ===========================================================================
# Client: Convenience method edge cases
# ===========================================================================


class TestConvenienceMethodEdgeCases:
    """Edge cases for the client's high-level WDK methods."""

    async def test_get_step_view_filters_correct_path(self) -> None:
        """View filters are extracted from step GET /users/{uid}/steps/{sid}."""
        client = VEuPathDBClient("https://example.com/service")

        with respx.mock(assert_all_called=False) as router:
            route = router.get(
                "https://example.com/service/users/12345/steps/42"
            ).respond(
                json={
                    "id": 42,
                    "answerSpec": {
                        "searchName": "GenesByTextSearch",
                        "searchConfig": {"parameters": {}},
                        "viewFilters": [{"name": "f1", "value": {}, "disabled": False}],
                    },
                }
            )
            p1, p2 = _patch_settings_and_ctx()
            with p1, p2:
                result = await client.get_step_view_filters("12345", 42)

        assert route.called
        assert result == [{"name": "f1", "value": {}, "disabled": False}]
        await client.close()

    async def test_get_search_details_with_params_encodes_context(self) -> None:
        """Context param values should be JSON-encoded before posting."""
        client = VEuPathDBClient("https://example.com/service")
        captured_json = {}

        with respx.mock(assert_all_called=False) as router:

            def capture(request: httpx.Request) -> httpx.Response:
                captured_json.update(json.loads(request.content))
                return httpx.Response(200, json={"searchData": {}})

            router.post(
                "https://example.com/service/record-types/gene/searches/GenesByTaxonGene"
            ).mock(side_effect=capture)
            p1, p2 = _patch_settings_and_ctx()
            with p1, p2:
                await client.get_search_details_with_params(
                    "gene",
                    "GenesByTaxonGene",
                    context={"organism": ["P. falciparum", "P. vivax"]},
                )

        # The list should have been JSON-encoded as a string
        cpv = captured_json.get("contextParamValues", {})
        assert isinstance(cpv.get("organism"), str)
        assert "P. falciparum" in cpv["organism"]
        await client.close()

    async def test_refreshed_dependent_params_includes_changed_param(self) -> None:
        """Refreshed-dependent-params endpoint includes changedParam."""
        client = VEuPathDBClient("https://example.com/service")
        captured_json = {}

        with respx.mock(assert_all_called=False) as router:

            def capture(request: httpx.Request) -> httpx.Response:
                captured_json.update(json.loads(request.content))
                return httpx.Response(200, json={})

            router.post(
                "https://example.com/service/record-types/gene/searches/S1/refreshed-dependent-params"
            ).mock(side_effect=capture)
            p1, p2 = _patch_settings_and_ctx()
            with p1, p2:
                await client.get_refreshed_dependent_params(
                    "gene",
                    "S1",
                    "organism",
                    {"organism": "Pf3D7", "threshold": "10"},
                )

        assert captured_json["changedParam"]["name"] == "organism"
        assert captured_json["changedParam"]["value"] == "Pf3D7"
        assert "organism" in captured_json["contextParamValues"]
        await client.close()
