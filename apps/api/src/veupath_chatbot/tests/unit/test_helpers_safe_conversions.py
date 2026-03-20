"""Tests for safe_int, safe_float, extract_wdk_id, coerce_step_id in helpers.py."""

import pytest

from veupath_chatbot.platform.errors import DataParsingError
from veupath_chatbot.services.experiment.helpers import (
    coerce_step_id,
    extract_wdk_id,
    safe_float,
    safe_int,
)


class TestSafeInt:
    def test_int_passthrough(self) -> None:
        assert safe_int(42) == 42

    def test_float_truncates(self) -> None:
        assert safe_int(3.9) == 3

    def test_string_numeric(self) -> None:
        assert safe_int("7") == 7

    def test_string_float(self) -> None:
        assert safe_int("3.14") == 3

    def test_none_returns_default(self) -> None:
        assert safe_int(None) == 0

    def test_non_numeric_string_returns_default(self) -> None:
        assert safe_int("abc") == 0

    def test_custom_default(self) -> None:
        assert safe_int("abc", default=-1) == -1

    def test_empty_string_returns_default(self) -> None:
        assert safe_int("") == 0

    def test_zero(self) -> None:
        assert safe_int(0) == 0

    def test_negative_int(self) -> None:
        assert safe_int(-5) == -5

    def test_negative_string(self) -> None:
        assert safe_int("-3") == -3

    def test_bool_true(self) -> None:
        # bool is subclass of int in Python
        assert safe_int(True) == 1

    def test_list_returns_default(self) -> None:
        assert safe_int([1, 2]) == 0

    def test_inf_returns_default(self) -> None:
        assert safe_int(float("inf")) == 0

    def test_nan_returns_default(self) -> None:
        assert safe_int(float("nan")) == 0


class TestSafeFloat:
    def test_int_to_float(self) -> None:
        assert safe_float(42) == 42.0

    def test_float_passthrough(self) -> None:
        assert safe_float(3.14) == 3.14

    def test_string_numeric(self) -> None:
        assert safe_float("2.718") == 2.718

    def test_none_returns_default(self) -> None:
        assert safe_float(None) == 0.0

    def test_non_numeric_string_returns_default(self) -> None:
        assert safe_float("abc") == 0.0

    def test_custom_default(self) -> None:
        assert safe_float("abc", default=-1.0) == -1.0

    def test_empty_string_returns_default(self) -> None:
        assert safe_float("") == 0.0

    def test_inf_returns_default(self) -> None:
        assert safe_float(float("inf")) == 0.0

    def test_negative_inf_returns_default(self) -> None:
        assert safe_float(float("-inf")) == 0.0

    def test_nan_returns_default(self) -> None:
        assert safe_float(float("nan")) == 0.0

    def test_zero(self) -> None:
        assert safe_float(0) == 0.0

    def test_negative_float(self) -> None:
        assert safe_float(-3.5) == -3.5

    def test_negative_string(self) -> None:
        assert safe_float("-2.5") == -2.5

    def test_list_returns_default(self) -> None:
        assert safe_float([1]) == 0.0

    def test_string_inf_returns_default(self) -> None:
        assert safe_float("inf") == 0.0

    def test_string_nan_returns_default(self) -> None:
        assert safe_float("nan") == 0.0


class TestExtractWdkId:
    def test_extracts_int_id(self) -> None:
        assert extract_wdk_id({"id": 42}) == 42

    def test_custom_key(self) -> None:
        assert extract_wdk_id({"strategyId": 99}, key="strategyId") == 99

    def test_none_payload(self) -> None:
        assert extract_wdk_id(None) is None

    def test_missing_key(self) -> None:
        assert extract_wdk_id({"other": 1}) is None

    def test_string_id_returns_none(self) -> None:
        assert extract_wdk_id({"id": "42"}) is None

    def test_empty_dict(self) -> None:
        assert extract_wdk_id({}) is None

    def test_non_dict_payload(self) -> None:
        assert extract_wdk_id("not a dict") is None

    def test_zero_id(self) -> None:
        assert extract_wdk_id({"id": 0}) == 0


class TestCoerceStepId:
    def test_extracts_valid_step_id(self) -> None:
        assert coerce_step_id({"id": 123}) == 123

    def test_raises_on_missing_id(self) -> None:
        with pytest.raises(DataParsingError, match="Failed to extract step ID"):
            coerce_step_id({})

    def test_raises_on_none_payload(self) -> None:
        with pytest.raises(DataParsingError, match="Failed to extract step ID"):
            coerce_step_id(None)

    def test_raises_on_string_id(self) -> None:
        with pytest.raises(DataParsingError, match="Failed to extract step ID"):
            coerce_step_id({"id": "abc"})
