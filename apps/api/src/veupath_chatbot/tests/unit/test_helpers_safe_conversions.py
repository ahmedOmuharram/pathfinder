"""Tests for safe_int and safe_float in helpers.py."""

from veupath_chatbot.services.experiment.helpers import (
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


