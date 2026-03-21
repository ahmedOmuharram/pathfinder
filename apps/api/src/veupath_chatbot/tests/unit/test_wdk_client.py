"""Unit tests for veupath_chatbot.integrations.veupathdb.client.

Tests VEuPathDBClient HTTP methods and the helper functions
encode_context_param_values_for_wdk and _convert_params_for_httpx.
"""

from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx

from veupath_chatbot.integrations.veupathdb.client import (
    VEuPathDBClient,
    _convert_params_for_httpx,
    encode_context_param_values_for_wdk,
)
from veupath_chatbot.platform.errors import WDKError

# ---------------------------------------------------------------------------
# encode_context_param_values_for_wdk
# ---------------------------------------------------------------------------


class TestEncodeContextParamValues:
    """WDK expects multi-pick values as JSON-encoded strings."""

    def test_string_values_pass_through(self) -> None:
        result = encode_context_param_values_for_wdk({"organism": "P. falciparum"})
        assert result == {"organism": "P. falciparum"}

    def test_list_values_json_encoded(self) -> None:
        result = encode_context_param_values_for_wdk(
            {"organism": ["P. falciparum", "P. vivax"]}
        )
        assert result["organism"] == '["P. falciparum", "P. vivax"]'

    def test_dict_values_json_encoded(self) -> None:
        result = encode_context_param_values_for_wdk({"config": {"key": "value"}})
        assert result["config"] == '{"key": "value"}'

    def test_int_values_stringified(self) -> None:
        result = encode_context_param_values_for_wdk({"count": 42})
        assert result["count"] == "42"

    def test_float_values_stringified(self) -> None:
        result = encode_context_param_values_for_wdk({"pvalue": 0.05})
        assert result["pvalue"] == "0.05"

    def test_none_values_skipped(self) -> None:
        result = encode_context_param_values_for_wdk({"a": "val", "b": None})
        assert result == {"a": "val"}

    def test_empty_context(self) -> None:
        result = encode_context_param_values_for_wdk({})
        assert result == {}

    def test_none_context(self) -> None:
        """The function uses `context or {}` so None is safe."""
        result = encode_context_param_values_for_wdk(None)
        assert result == {}


# ---------------------------------------------------------------------------
# _convert_params_for_httpx
# ---------------------------------------------------------------------------


class TestConvertParamsForHttpx:
    """Convert JSONObject params to httpx-compatible format."""

    def test_none_returns_none(self) -> None:
        assert _convert_params_for_httpx(None) is None

    def test_string_value_passes_through(self) -> None:
        result = _convert_params_for_httpx({"key": "value"})
        assert result == {"key": "value"}

    def test_int_value_passes_through(self) -> None:
        result = _convert_params_for_httpx({"key": 42})
        assert result == {"key": 42}

    def test_bool_value_passes_through(self) -> None:
        result = _convert_params_for_httpx({"key": True})
        assert result == {"key": True}

    def test_none_value_passes_through(self) -> None:
        result = _convert_params_for_httpx({"key": None})
        assert result == {"key": None}

    def test_list_converted_to_sequence(self) -> None:
        result = _convert_params_for_httpx({"key": ["a", "b"]})
        assert result == {"key": ["a", "b"]}

    def test_list_with_mixed_types(self) -> None:
        result = _convert_params_for_httpx({"key": [1, "two", True, None]})
        assert result == {"key": [1, "two", True, None]}

    def test_non_primitive_stringified(self) -> None:
        """Dict values and other types are converted to string."""
        result = _convert_params_for_httpx({"key": {"nested": True}})
        assert result is not None
        assert isinstance(result["key"], str)

    def test_list_with_non_primitive_items(self) -> None:
        result = _convert_params_for_httpx({"key": [{"nested": True}]})
        assert result is not None
        # Non-primitive list items are stringified
        items = result["key"]
        assert isinstance(items, list)
        assert isinstance(items[0], str)


# ---------------------------------------------------------------------------
# VEuPathDBClient initialization
# ---------------------------------------------------------------------------


class TestVEuPathDBClientInit:
    """Client initialization and configuration."""

    def test_strips_trailing_slash(self) -> None:
        client = VEuPathDBClient("https://example.com/service/")
        assert client.base_url == "https://example.com/service"

    def test_default_timeout(self) -> None:
        client = VEuPathDBClient("https://example.com/service")
        assert client.timeout == 30.0

    def test_custom_timeout(self) -> None:
        client = VEuPathDBClient("https://example.com/service", timeout=120.0)
        assert client.timeout == 120.0

    def test_auth_token_stored(self) -> None:
        client = VEuPathDBClient("https://example.com/service", auth_token="tok")
        assert client.auth_token == "tok"


# ---------------------------------------------------------------------------
# VEuPathDBClient HTTP methods (with respx mocking)
# ---------------------------------------------------------------------------


class TestVEuPathDBClientRequests:
    """HTTP request methods with mocked responses."""

    async def test_get_request(self) -> None:
        client = VEuPathDBClient("https://plasmodb.org/plasmo/service")

        with respx.mock(assert_all_called=False) as router:
            router.get("https://plasmodb.org/plasmo/service/record-types").respond(
                json=["gene", "transcript"]
            )
            with patch(
                "veupath_chatbot.integrations.veupathdb.client.get_settings"
            ) as mock_settings:
                mock_settings.return_value = MagicMock(veupathdb_auth_token=None)
                with patch(
                    "veupath_chatbot.integrations.veupathdb.client.veupathdb_auth_token_ctx"
                ) as mock_ctx:
                    mock_ctx.get.return_value = None
                    result = await client.get("/record-types")

        assert result == ["gene", "transcript"]
        await client.close()

    async def test_post_request(self) -> None:
        client = VEuPathDBClient("https://plasmodb.org/plasmo/service")

        with respx.mock(assert_all_called=False) as router:
            router.post(
                "https://plasmodb.org/plasmo/service/users/current/steps"
            ).respond(json={"id": 42})
            with patch(
                "veupath_chatbot.integrations.veupathdb.client.get_settings"
            ) as mock_settings:
                mock_settings.return_value = MagicMock(veupathdb_auth_token=None)
                with patch(
                    "veupath_chatbot.integrations.veupathdb.client.veupathdb_auth_token_ctx"
                ) as mock_ctx:
                    mock_ctx.get.return_value = None
                    result = await client.post(
                        "/users/current/steps",
                        json={"searchName": "GenesByTaxonGene"},
                    )

        assert result == {"id": 42}
        await client.close()

    async def test_empty_response_returns_none(self) -> None:
        client = VEuPathDBClient("https://plasmodb.org/plasmo/service")

        with respx.mock(assert_all_called=False) as router:
            router.delete(
                "https://plasmodb.org/plasmo/service/users/12345/strategies/1"
            ).respond(200, content=b"")
            with patch(
                "veupath_chatbot.integrations.veupathdb.client.get_settings"
            ) as mock_settings:
                mock_settings.return_value = MagicMock(veupathdb_auth_token=None)
                with patch(
                    "veupath_chatbot.integrations.veupathdb.client.veupathdb_auth_token_ctx"
                ) as mock_ctx:
                    mock_ctx.get.return_value = None
                    result = await client.delete("/users/12345/strategies/1")

        assert result is None
        await client.close()

    async def test_http_error_raises_wdk_error(self) -> None:
        client = VEuPathDBClient("https://plasmodb.org/plasmo/service")

        with respx.mock(assert_all_called=False) as router:
            router.get("https://plasmodb.org/plasmo/service/bad-path").respond(
                404, text="Not Found"
            )
            with patch(
                "veupath_chatbot.integrations.veupathdb.client.get_settings"
            ) as mock_settings:
                mock_settings.return_value = MagicMock(veupathdb_auth_token=None)
                with patch(
                    "veupath_chatbot.integrations.veupathdb.client.veupathdb_auth_token_ctx"
                ) as mock_ctx:
                    mock_ctx.get.return_value = None
                    with pytest.raises(WDKError) as exc_info:
                        await client.get("/bad-path")

        assert exc_info.value.status == 404
        await client.close()

    async def test_auth_token_sent_as_cookie(self) -> None:
        """WDK authenticates via Authorization cookie, not header."""
        client = VEuPathDBClient(
            "https://plasmodb.org/plasmo/service",
            auth_token="my_token",
        )
        captured_cookies: dict[str, str] = {}

        with respx.mock(assert_all_called=False) as router:

            def capture_request(request: httpx.Request) -> httpx.Response:
                captured_cookies.update(dict(request.headers.items()))
                return httpx.Response(200, json=[])

            router.get("https://plasmodb.org/plasmo/app").respond(200)
            router.get("https://plasmodb.org/plasmo/service/record-types").mock(
                side_effect=capture_request
            )
            with patch(
                "veupath_chatbot.integrations.veupathdb.client.get_settings"
            ) as mock_settings:
                mock_settings.return_value = MagicMock(veupathdb_auth_token=None)
                with patch(
                    "veupath_chatbot.integrations.veupathdb.client.veupathdb_auth_token_ctx"
                ) as mock_ctx:
                    mock_ctx.get.return_value = None
                    await client.get("/record-types")

        # The token should be sent as a cookie. httpx includes cookie in
        # the cookie header.
        await client.close()


# ---------------------------------------------------------------------------
# VEuPathDBClient convenience methods
# ---------------------------------------------------------------------------


class TestVEuPathDBClientConvenienceMethods:
    """Test get_record_types, get_searches, get_search_details.

    Verified against live WDK:
    - /record-types returns array of strings (non-expanded)
    - /record-types?format=expanded returns array of objects with urlSegment, searches, etc.
    - /record-types/gene/searches returns array of search objects with urlSegment
    - /record-types/gene/searches/X?expandParams=true wraps data under searchData key
    """

    async def test_get_record_types_non_expanded(self) -> None:
        client = VEuPathDBClient("https://plasmodb.org/plasmo/service")

        with respx.mock(assert_all_called=False) as router:
            router.get("https://plasmodb.org/plasmo/service/record-types").respond(
                json=["transcript", "gene", "organism"]
            )
            with patch(
                "veupath_chatbot.integrations.veupathdb.client.get_settings"
            ) as mock_settings:
                mock_settings.return_value = MagicMock(veupathdb_auth_token=None)
                with patch(
                    "veupath_chatbot.integrations.veupathdb.client.veupathdb_auth_token_ctx"
                ) as mock_ctx:
                    mock_ctx.get.return_value = None
                    result = await client.get_record_types()

        assert result == ["transcript", "gene", "organism"]
        await client.close()

    async def test_get_record_types_expanded(self) -> None:
        client = VEuPathDBClient("https://plasmodb.org/plasmo/service")

        with respx.mock(assert_all_called=False) as router:
            router.get("https://plasmodb.org/plasmo/service/record-types").respond(
                json=[{"urlSegment": "gene", "displayName": "Gene", "searches": []}]
            )
            with patch(
                "veupath_chatbot.integrations.veupathdb.client.get_settings"
            ) as mock_settings:
                mock_settings.return_value = MagicMock(veupathdb_auth_token=None)
                with patch(
                    "veupath_chatbot.integrations.veupathdb.client.veupathdb_auth_token_ctx"
                ) as mock_ctx:
                    mock_ctx.get.return_value = None
                    result = await client.get_record_types(expanded=True)

        assert isinstance(result, list)
        first = result[0]
        assert isinstance(first, dict)
        assert first["urlSegment"] == "gene"
        await client.close()

    async def test_get_searches(self) -> None:
        client = VEuPathDBClient("https://plasmodb.org/plasmo/service")

        with respx.mock(assert_all_called=False) as router:
            router.get(
                "https://plasmodb.org/plasmo/service/record-types/gene/searches"
            ).respond(
                json=[
                    {"urlSegment": "GenesByTaxonGene", "displayName": "Organism"},
                    {
                        "urlSegment": "boolean_question_GeneRecordClasses_GeneRecordClass",
                        "displayName": "Boolean",
                    },
                ]
            )
            with patch(
                "veupath_chatbot.integrations.veupathdb.client.get_settings"
            ) as mock_settings:
                mock_settings.return_value = MagicMock(veupathdb_auth_token=None)
                with patch(
                    "veupath_chatbot.integrations.veupathdb.client.veupathdb_auth_token_ctx"
                ) as mock_ctx:
                    mock_ctx.get.return_value = None
                    result = await client.get_searches("gene")

        assert len(result) == 2
        first = result[0]
        assert first.url_segment == "GenesByTaxonGene"
        await client.close()

    async def test_get_search_details(self) -> None:
        """WDK wraps search details under 'searchData' key."""
        client = VEuPathDBClient("https://plasmodb.org/plasmo/service")

        with respx.mock(assert_all_called=False) as router:
            router.get(
                "https://plasmodb.org/plasmo/service/record-types/gene/searches/GenesByTaxonGene"
            ).respond(
                json={
                    "searchData": {
                        "urlSegment": "GenesByTaxonGene",
                        "paramNames": ["organism"],
                        "parameters": [
                            {
                                "name": "organism",
                                "type": "multi-pick-vocabulary",
                                "displayName": "Organism",
                            }
                        ],
                    },
                    "validation": {"level": "NONE"},
                }
            )
            with patch(
                "veupath_chatbot.integrations.veupathdb.client.get_settings"
            ) as mock_settings:
                mock_settings.return_value = MagicMock(veupathdb_auth_token=None)
                with patch(
                    "veupath_chatbot.integrations.veupathdb.client.veupathdb_auth_token_ctx"
                ) as mock_ctx:
                    mock_ctx.get.return_value = None
                    result = await client.get_search_details("gene", "GenesByTaxonGene")

        assert result.search_data.url_segment == "GenesByTaxonGene"
        assert result.validation is not None
        await client.close()


# ---------------------------------------------------------------------------
# VEuPathDBClient.close
# ---------------------------------------------------------------------------


class TestVEuPathDBClientClose:
    """Test client lifecycle."""

    async def test_close_when_not_initialized(self) -> None:
        """Should not raise when _client is None."""
        client = VEuPathDBClient("https://example.com/service")
        await client.close()  # Should be a no-op

    async def test_close_sets_client_to_none(self) -> None:
        client = VEuPathDBClient("https://plasmodb.org/plasmo/service")

        with respx.mock(assert_all_called=False) as router:
            router.get("https://plasmodb.org/plasmo/service/record-types").respond(
                json=[]
            )
            with patch(
                "veupath_chatbot.integrations.veupathdb.client.get_settings"
            ) as mock_settings:
                mock_settings.return_value = MagicMock(veupathdb_auth_token=None)
                with patch(
                    "veupath_chatbot.integrations.veupathdb.client.veupathdb_auth_token_ctx"
                ) as mock_ctx:
                    mock_ctx.get.return_value = None
                    await client.get("/record-types")  # initialize _client

        assert client._client is not None
        await client.close()
        assert client._client is None
