"""Tests for extract_wdk_id and coerce_step_id helpers."""

import pytest

from veupath_chatbot.platform.errors import DataParsingError
from veupath_chatbot.services.experiment.helpers import (
    coerce_step_id,
    extract_wdk_id,
    safe_float,
    safe_int,
)

# ── extract_wdk_id ──


class TestExtractWdkId:
    def test_extracts_int_id(self) -> None:
        assert extract_wdk_id({"id": 42}) == 42

    def test_returns_none_for_missing_key(self) -> None:
        assert extract_wdk_id({"other": 42}) is None

    def test_returns_none_for_none_payload(self) -> None:
        assert extract_wdk_id(None) is None

    def test_returns_none_for_non_dict(self) -> None:
        assert extract_wdk_id(None) is None

    def test_returns_none_for_string_value(self) -> None:
        assert extract_wdk_id({"id": "42"}) is None

    def test_returns_none_for_float_value(self) -> None:
        assert extract_wdk_id({"id": 42.5}) is None

    def test_custom_key(self) -> None:
        assert extract_wdk_id({"strategyId": 99}, key="strategyId") == 99

    def test_custom_key_missing(self) -> None:
        assert extract_wdk_id({"id": 99}, key="strategyId") is None

    def test_zero_is_valid(self) -> None:
        assert extract_wdk_id({"id": 0}) == 0

    def test_negative_is_valid(self) -> None:
        assert extract_wdk_id({"id": -1}) == -1

    def test_empty_dict(self) -> None:
        assert extract_wdk_id({}) is None


# ── coerce_step_id ──


class TestCoerceStepId:
    def test_extracts_step_id(self) -> None:
        assert coerce_step_id({"id": 123}) == 123

    def test_raises_on_missing_id(self) -> None:
        with pytest.raises(DataParsingError, match="step ID"):
            coerce_step_id({"other": 123})

    def test_raises_on_none(self) -> None:
        with pytest.raises(DataParsingError, match="step ID"):
            coerce_step_id(None)

    def test_raises_on_string_id(self) -> None:
        with pytest.raises(DataParsingError, match="step ID"):
            coerce_step_id({"id": "not_an_int"})


# ── safe_int ──


class TestSafeInt:
    def test_int_passthrough(self) -> None:
        assert safe_int(42) == 42

    def test_float_to_int(self) -> None:
        assert safe_int(3.7) == 3

    def test_string_to_int(self) -> None:
        assert safe_int("10") == 10

    def test_invalid_string(self) -> None:
        assert safe_int("abc") == 0

    def test_none_returns_default(self) -> None:
        assert safe_int(None) == 0

    def test_custom_default(self) -> None:
        assert safe_int(None, default=-1) == -1

    def test_bool_is_int(self) -> None:
        assert safe_int(True) == 1


# ── safe_float ──


class TestSafeFloat:
    def test_float_passthrough(self) -> None:
        assert safe_float(3.14) == 3.14

    def test_int_to_float(self) -> None:
        assert safe_float(5) == 5.0

    def test_string_to_float(self) -> None:
        assert safe_float("2.5") == 2.5

    def test_invalid_string(self) -> None:
        assert safe_float("abc") == 0.0

    def test_none_returns_default(self) -> None:
        assert safe_float(None) == 0.0

    def test_custom_default(self) -> None:
        assert safe_float(None, default=-1.0) == -1.0

    def test_inf_returns_default(self) -> None:
        assert safe_float(float("inf")) == 0.0

    def test_nan_returns_default(self) -> None:
        assert safe_float(float("nan")) == 0.0

    def test_neg_inf_returns_default(self) -> None:
        assert safe_float(float("-inf")) == 0.0
