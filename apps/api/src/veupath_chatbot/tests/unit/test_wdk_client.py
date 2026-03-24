"""Unit tests for pure-logic functions in the WDK client layer.

Tests encode_wdk_params, _convert_params_for_httpx, and VEuPathDBClient
initialization / close lifecycle. HTTP method tests live in
tests/integration/test_wdk_client.py.
"""

from veupath_chatbot.integrations.veupathdb.client import (
    VEuPathDBClient,
    _convert_params_for_httpx,
)
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    encode_wdk_params,
)

# ---------------------------------------------------------------------------
# encode_wdk_params
# ---------------------------------------------------------------------------


class TestEncodeContextParamValues:
    """WDK expects multi-pick values as JSON-encoded strings."""

    def test_string_values_pass_through(self) -> None:
        result = encode_wdk_params({"organism": "P. falciparum"})
        assert result == {"organism": "P. falciparum"}

    def test_list_values_json_encoded(self) -> None:
        result = encode_wdk_params({"organism": ["P. falciparum", "P. vivax"]})
        assert result["organism"] == '["P. falciparum", "P. vivax"]'

    def test_dict_values_json_encoded(self) -> None:
        result = encode_wdk_params({"config": {"key": "value"}})
        assert result["config"] == '{"key": "value"}'

    def test_int_values_stringified(self) -> None:
        result = encode_wdk_params({"count": 42})
        assert result["count"] == "42"

    def test_float_values_stringified(self) -> None:
        result = encode_wdk_params({"pvalue": 0.05})
        assert result["pvalue"] == "0.05"

    def test_none_values_skipped(self) -> None:
        result = encode_wdk_params({"a": "val", "b": None})
        assert result == {"a": "val"}

    def test_empty_context(self) -> None:
        result = encode_wdk_params({})
        assert result == {}

    def test_none_context(self) -> None:
        """The function uses `context or {}` so None is safe."""
        result = encode_wdk_params(None)
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
# VEuPathDBClient.close
# ---------------------------------------------------------------------------


class TestVEuPathDBClientClose:
    """Test client lifecycle."""

    async def test_close_when_not_initialized(self) -> None:
        """Should not raise when _client is None."""
        client = VEuPathDBClient("https://example.com/service")
        await client.close()  # Should be a no-op

    async def test_close_sets_client_to_none(self) -> None:
        """After manual client initialization and close, _client is None."""
        client = VEuPathDBClient("https://example.com/service")
        # Manually initialize the internal httpx client
        internal = await client._get_client()
        assert internal is not None
        assert client._client is not None
        await client.close()
        assert client._client is None
