"""Tests for domain/parameters/_value_helpers.py."""

import pytest

from veupath_chatbot.domain.parameters._value_helpers import (
    handle_empty,
    stringify,
    validate_multi_count,
    validate_single_required,
)
from veupath_chatbot.domain.parameters.vocab_utils import match_vocab_value
from veupath_chatbot.platform.errors import ValidationError
from veupath_chatbot.tests.fixtures.builders import ParamSpecConfig, make_param_spec


class TestStringify:
    def test_none(self) -> None:
        assert stringify(None) == ""

    def test_bool_true(self) -> None:
        assert stringify(True) == "true"

    def test_bool_false(self) -> None:
        assert stringify(False) == "false"

    def test_string(self) -> None:
        assert stringify("hello") == "hello"

    def test_integer(self) -> None:
        assert stringify(42) == "42"

    def test_float(self) -> None:
        assert stringify(3.14) == "3.14"

    def test_empty_string(self) -> None:
        assert stringify("") == ""


class TestHandleEmpty:
    def test_allow_empty_returns_empty_string(self) -> None:
        spec = make_param_spec(ParamSpecConfig(allow_empty=True))
        assert handle_empty(spec, None) == ""

    def test_allow_empty_returns_empty_string_regardless_of_value(self) -> None:
        spec = make_param_spec(ParamSpecConfig(allow_empty=True))
        assert handle_empty(spec, "anything") == ""

    def test_multi_pick_not_allow_empty_raises(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(param_type="multi-pick-vocabulary", allow_empty=False)
        )
        with pytest.raises(ValidationError) as exc_info:
            handle_empty(spec, None)
        assert "requires a value" in (exc_info.value.detail or "")

    def test_single_pick_not_allow_empty_raises(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(param_type="single-pick-vocabulary", allow_empty=False)
        )
        with pytest.raises(ValidationError) as exc_info:
            handle_empty(spec, None)
        assert "requires a value" in (exc_info.value.detail or "")

    def test_number_not_allow_empty_raises(self) -> None:
        spec = make_param_spec(ParamSpecConfig(param_type="number", allow_empty=False))
        with pytest.raises(ValidationError) as exc_info:
            handle_empty(spec, None)
        assert "requires a value" in (exc_info.value.detail or "")

    def test_string_not_allow_empty_raises(self) -> None:
        spec = make_param_spec(ParamSpecConfig(param_type="string", allow_empty=False))
        with pytest.raises(ValidationError) as exc_info:
            handle_empty(spec, None)
        assert "requires a value" in (exc_info.value.detail or "")

    def test_date_not_allow_empty_raises(self) -> None:
        spec = make_param_spec(ParamSpecConfig(param_type="date", allow_empty=False))
        with pytest.raises(ValidationError) as exc_info:
            handle_empty(spec, None)
        assert "requires a value" in (exc_info.value.detail or "")

    def test_number_range_not_allow_empty_raises(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(param_type="number-range", allow_empty=False)
        )
        with pytest.raises(ValidationError) as exc_info:
            handle_empty(spec, None)
        assert "requires a value" in (exc_info.value.detail or "")

    def test_filter_not_allow_empty_raises(self) -> None:
        spec = make_param_spec(ParamSpecConfig(param_type="filter", allow_empty=False))
        with pytest.raises(ValidationError) as exc_info:
            handle_empty(spec, None)
        assert "requires a value" in (exc_info.value.detail or "")


class TestValidateMultiCount:
    def test_empty_with_allow_empty_passes(self) -> None:
        spec = make_param_spec(ParamSpecConfig(allow_empty=True))
        validate_multi_count(spec, [])  # should not raise

    def test_below_min_raises(self) -> None:
        spec = make_param_spec(ParamSpecConfig(min_selected=2))
        with pytest.raises(ValidationError) as exc_info:
            validate_multi_count(spec, ["a"])
        assert "at least 2" in (exc_info.value.detail or "")

    def test_above_max_raises(self) -> None:
        spec = make_param_spec(ParamSpecConfig(max_selected=2))
        with pytest.raises(ValidationError) as exc_info:
            validate_multi_count(spec, ["a", "b", "c"])
        assert "at most 2" in (exc_info.value.detail or "")

    def test_at_min_passes(self) -> None:
        spec = make_param_spec(ParamSpecConfig(min_selected=2))
        validate_multi_count(spec, ["a", "b"])

    def test_at_max_passes(self) -> None:
        spec = make_param_spec(ParamSpecConfig(max_selected=3))
        validate_multi_count(spec, ["a", "b", "c"])

    def test_no_constraints_passes(self) -> None:
        spec = make_param_spec()
        validate_multi_count(spec, ["a", "b", "c", "d"])

    def test_zero_min_passes_with_empty(self) -> None:
        spec = make_param_spec(ParamSpecConfig(min_selected=0))
        validate_multi_count(spec, [])


class TestValidateSingleRequired:
    def test_allow_empty_passes(self) -> None:
        spec = make_param_spec(ParamSpecConfig(allow_empty=True))
        validate_single_required(spec)  # should not raise

    def test_min_zero_passes(self) -> None:
        spec = make_param_spec(ParamSpecConfig(min_selected=0))
        validate_single_required(spec)

    def test_min_negative_passes(self) -> None:
        spec = make_param_spec(ParamSpecConfig(min_selected=-1))
        validate_single_required(spec)

    def test_no_min_raises(self) -> None:
        spec = make_param_spec()
        with pytest.raises(ValidationError) as exc_info:
            validate_single_required(spec)
        assert "requires a value" in (exc_info.value.detail or "")

    def test_min_one_raises(self) -> None:
        spec = make_param_spec(ParamSpecConfig(min_selected=1))
        with pytest.raises(ValidationError) as exc_info:
            validate_single_required(spec)
        assert "requires a value" in (exc_info.value.detail or "")


class TestMatchVocabValue:
    def test_with_list_vocab(self) -> None:
        assert (
            match_vocab_value(
                vocab=[["val1", "Display 1"], ["val2", "Display 2"]],
                param_name="test_param",
                value="Display 1",
            )
            == "val1"
        )

    def test_no_vocab_passthrough(self) -> None:
        assert (
            match_vocab_value(vocab=None, param_name="test_param", value="anything")
            == "anything"
        )

    def test_empty_string_vocab_value_matches(self) -> None:
        """Vocabulary entries where the term value is '' should match correctly."""
        result = match_vocab_value(
            vocab=[["", "No selection"], ["yes", "Yes"]],
            param_name="test_param",
            value="No selection",
        )
        assert result == ""

    def test_empty_string_vocab_value_direct_match(self) -> None:
        """Matching the empty string directly against a vocab entry with term ''."""
        result = match_vocab_value(
            vocab=[["", "No selection"], ["yes", "Yes"]],
            param_name="test_param",
            value="",
        )
        assert result == ""

    def test_invalid_value_raises(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            match_vocab_value(
                vocab=[["a", "A"]], param_name="test_param", value="nonexistent"
            )
        assert "does not accept" in (exc_info.value.detail or "")
