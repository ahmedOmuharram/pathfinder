"""Tests for WDK client parameter encoding functions.

Verifies that encode_wdk_params() and
_convert_params_for_httpx() produce correct wire-format values.
These pure functions are critical: wrong encoding silently corrupts
ALL WDK API calls.
"""

from veupath_chatbot.integrations.veupathdb.client import (
    _convert_params_for_httpx,
)
from veupath_chatbot.integrations.veupathdb.wdk_models import encode_wdk_params


class TestEncodeContextParamValues:
    """Tests for encode_wdk_params()."""

    def test_string_values_pass_through(self) -> None:
        result = encode_wdk_params({"org": "Plasmodium falciparum"})
        assert result == {"org": "Plasmodium falciparum"}

    def test_list_becomes_json_string(self) -> None:
        """Multi-pick values must be JSON-encoded strings for WDK."""
        result = encode_wdk_params({"orgs": ["pfal", "pviv"]})
        assert result == {"orgs": '["pfal", "pviv"]'}

    def test_dict_becomes_json_string(self) -> None:
        result = encode_wdk_params({"filter": {"min": 0, "max": 100}})
        assert result == {"filter": '{"min": 0, "max": 100}'}

    def test_none_values_omitted(self) -> None:
        """None values should be dropped entirely."""
        result = encode_wdk_params({"a": "val", "b": None})
        assert result == {"a": "val"}
        assert "b" not in result

    def test_int_becomes_string(self) -> None:
        result = encode_wdk_params({"threshold": 42})
        assert result == {"threshold": "42"}

    def test_float_becomes_string(self) -> None:
        result = encode_wdk_params({"pvalue": 0.05})
        assert result == {"pvalue": "0.05"}

    def test_bool_becomes_string(self) -> None:
        result = encode_wdk_params({"flag": True})
        assert result == {"flag": "true"}

    def test_empty_context(self) -> None:
        assert encode_wdk_params({}) == {}

    def test_none_context(self) -> None:
        assert encode_wdk_params(None) == {}

    def test_empty_string_preserved(self) -> None:
        """Empty strings are valid WDK param values."""
        result = encode_wdk_params({"q": ""})
        assert result == {"q": ""}

    def test_nested_list_in_dict(self) -> None:
        """Dicts with nested lists should serialize to JSON."""
        context = {"complex": {"values": [1, 2, 3]}}
        result = encode_wdk_params(context)
        assert result["complex"] == '{"values": [1, 2, 3]}'

    def test_empty_list_becomes_json(self) -> None:
        result = encode_wdk_params({"orgs": []})
        assert result == {"orgs": "[]"}

    def test_multiple_keys_independent(self) -> None:
        context = {"a": "str", "b": [1, 2], "c": None, "d": 42}
        result = encode_wdk_params(context)
        assert result == {"a": "str", "b": "[1, 2]", "d": "42"}


class TestConvertParamsForHttpx:
    """Tests for _convert_params_for_httpx()."""

    def test_none_returns_none(self) -> None:
        assert _convert_params_for_httpx(None) is None

    def test_string_values_pass_through(self) -> None:
        result = _convert_params_for_httpx({"format": "expanded"})
        assert result == {"format": "expanded"}

    def test_int_values_pass_through(self) -> None:
        result = _convert_params_for_httpx({"limit": 10})
        assert result is not None
        assert result["limit"] == 10

    def test_float_values_pass_through(self) -> None:
        result = _convert_params_for_httpx({"threshold": 0.5})
        assert result is not None
        assert result["threshold"] == 0.5

    def test_bool_values_pass_through(self) -> None:
        result = _convert_params_for_httpx({"expandParams": True})
        assert result is not None
        assert result["expandParams"] is True

    def test_none_value_preserved(self) -> None:
        result = _convert_params_for_httpx({"key": None})
        assert result is not None
        assert result["key"] is None

    def test_list_of_strings(self) -> None:
        result = _convert_params_for_httpx({"ids": ["a", "b", "c"]})
        assert result is not None
        assert list(result["ids"]) == ["a", "b", "c"]

    def test_list_with_mixed_types(self) -> None:
        """List items that aren't primitives should be stringified."""
        result = _convert_params_for_httpx({"data": [1, "two", {"nested": True}]})
        assert result is not None
        converted = list(result["data"])
        assert converted[0] == 1
        assert converted[1] == "two"
        assert isinstance(converted[2], str)  # dict converted to string

    def test_dict_value_becomes_string(self) -> None:
        """Non-primitive values should be stringified."""
        result = _convert_params_for_httpx({"obj": {"nested": True}})
        assert result is not None
        assert isinstance(result["obj"], str)

    def test_empty_params(self) -> None:
        result = _convert_params_for_httpx({})
        assert result == {}
