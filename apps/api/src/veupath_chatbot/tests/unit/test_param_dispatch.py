"""Tests for the shared param-type dispatch mechanism.

Verifies that ``_value_helpers.process_value()`` correctly routes each
param_type through its handler and returns the appropriate ``ProcessedParam``
with the correct ``ParamKind``.
"""

import pytest

from veupath_chatbot.domain.parameters._value_helpers import (
    ParamKind,
    process_value,
)
from veupath_chatbot.platform.errors import ValidationError
from veupath_chatbot.tests.fixtures.builders import make_param_spec


# ---------------------------------------------------------------------------
# ParamKind enum
# ---------------------------------------------------------------------------
class TestParamKind:
    def test_all_kinds_distinct(self) -> None:
        kinds = list(ParamKind)
        assert len(kinds) == len(set(kinds))


# ---------------------------------------------------------------------------
# multi-pick-vocabulary dispatch
# ---------------------------------------------------------------------------
class TestDispatchMultiPick:
    def test_returns_list(self) -> None:
        spec = make_param_spec(
            name="p",
            param_type="multi-pick-vocabulary",
            vocabulary=[["a", "A"], ["b", "B"]],
        )
        result = process_value(spec, ["A", "B"])
        assert result.kind is ParamKind.MULTI_PICK
        assert result.value == ["a", "b"]

    def test_csv_string_decoded(self) -> None:
        spec = make_param_spec(
            name="p",
            param_type="multi-pick-vocabulary",
            vocabulary=[["x", "x"], ["y", "y"]],
        )
        result = process_value(spec, "x,y")
        assert result.kind is ParamKind.MULTI_PICK
        assert result.value == ["x", "y"]

    def test_validates_min_count(self) -> None:
        spec = make_param_spec(
            name="p",
            param_type="multi-pick-vocabulary",
            min_selected=2,
            vocabulary=[["a", "a"]],
        )
        with pytest.raises(ValidationError) as exc_info:
            process_value(spec, ["a"])
        assert "at least 2" in (exc_info.value.detail or "")

    def test_validates_max_count(self) -> None:
        spec = make_param_spec(
            name="p",
            param_type="multi-pick-vocabulary",
            max_selected=1,
            vocabulary=[["a", "a"], ["b", "b"]],
        )
        with pytest.raises(ValidationError) as exc_info:
            process_value(spec, ["a", "b"])
        assert "at most 1" in (exc_info.value.detail or "")


# ---------------------------------------------------------------------------
# single-pick-vocabulary dispatch
# ---------------------------------------------------------------------------
class TestDispatchSinglePick:
    def test_string_value(self) -> None:
        spec = make_param_spec(
            name="p",
            param_type="single-pick-vocabulary",
            vocabulary=[["ring", "Ring"]],
        )
        result = process_value(spec, "Ring")
        assert result.kind is ParamKind.SINGLE_PICK
        assert result.value == "ring"

    def test_multiple_values_raises(self) -> None:
        spec = make_param_spec(
            name="p",
            param_type="single-pick-vocabulary",
            vocabulary=[["a", "A"], ["b", "B"]],
        )
        with pytest.raises(ValidationError) as exc_info:
            process_value(spec, ["A", "B"])
        assert "only one value" in (exc_info.value.detail or "")

    def test_empty_with_allow_empty(self) -> None:
        spec = make_param_spec(
            name="p",
            param_type="single-pick-vocabulary",
            allow_empty=True,
        )
        result = process_value(spec, "")
        assert result.kind is ParamKind.SINGLE_PICK
        assert result.value == ""

    def test_empty_without_allow_empty_raises(self) -> None:
        spec = make_param_spec(
            name="p",
            param_type="single-pick-vocabulary",
            allow_empty=False,
        )
        with pytest.raises(ValidationError) as exc_info:
            process_value(spec, "")
        assert "requires a value" in (exc_info.value.detail or "")


# ---------------------------------------------------------------------------
# scalar types
# ---------------------------------------------------------------------------
class TestDispatchScalar:
    @pytest.mark.parametrize("param_type", ["number", "date", "timestamp", "string"])
    def test_string_value(self, param_type: str) -> None:
        spec = make_param_spec(name="p", param_type=param_type)
        result = process_value(spec, "value")
        assert result.kind is ParamKind.SCALAR
        assert result.value == "value"

    @pytest.mark.parametrize("param_type", ["number", "date", "timestamp", "string"])
    def test_int_stringified(self, param_type: str) -> None:
        spec = make_param_spec(name="p", param_type=param_type)
        result = process_value(spec, 42)
        assert result.kind is ParamKind.SCALAR
        assert result.value == "42"

    @pytest.mark.parametrize("param_type", ["number", "date", "timestamp", "string"])
    def test_list_raises(self, param_type: str) -> None:
        spec = make_param_spec(name="p", param_type=param_type)
        with pytest.raises(ValidationError) as exc_info:
            process_value(spec, [1, 2])
        assert "scalar" in (exc_info.value.detail or "")


# ---------------------------------------------------------------------------
# range types
# ---------------------------------------------------------------------------
class TestDispatchRange:
    @pytest.mark.parametrize("param_type", ["number-range", "date-range"])
    def test_dict_value(self, param_type: str) -> None:
        spec = make_param_spec(name="p", param_type=param_type)
        result = process_value(spec, {"min": 1, "max": 10})
        assert result.kind is ParamKind.RANGE
        assert result.value == {"min": 1, "max": 10}

    @pytest.mark.parametrize("param_type", ["number-range", "date-range"])
    def test_list_pair_coerced(self, param_type: str) -> None:
        spec = make_param_spec(name="p", param_type=param_type)
        result = process_value(spec, [1, 10])
        assert result.kind is ParamKind.RANGE
        assert result.value == {"min": 1, "max": 10}

    @pytest.mark.parametrize("param_type", ["number-range", "date-range"])
    def test_invalid_raises(self, param_type: str) -> None:
        spec = make_param_spec(name="p", param_type=param_type)
        with pytest.raises(ValidationError) as exc_info:
            process_value(spec, "invalid")
        assert "must be a range" in (exc_info.value.detail or "")


# ---------------------------------------------------------------------------
# filter
# ---------------------------------------------------------------------------
class TestDispatchFilter:
    def test_dict_value(self) -> None:
        spec = make_param_spec(name="p", param_type="filter")
        result = process_value(spec, {"filters": []})
        assert result.kind is ParamKind.FILTER
        assert result.value == {"filters": []}

    def test_list_value(self) -> None:
        spec = make_param_spec(name="p", param_type="filter")
        result = process_value(spec, [{"field": "x"}])
        assert result.kind is ParamKind.FILTER
        assert result.value == [{"field": "x"}]

    def test_string_value(self) -> None:
        spec = make_param_spec(name="p", param_type="filter")
        result = process_value(spec, "filter_val")
        assert result.kind is ParamKind.FILTER
        assert result.value == "filter_val"


# ---------------------------------------------------------------------------
# input-dataset
# ---------------------------------------------------------------------------
class TestDispatchInputDataset:
    def test_single_list_item(self) -> None:
        spec = make_param_spec(name="p", param_type="input-dataset")
        result = process_value(spec, ["dataset_1"])
        assert result.kind is ParamKind.INPUT_DATASET
        assert result.value == "dataset_1"

    def test_multi_list_raises(self) -> None:
        spec = make_param_spec(name="p", param_type="input-dataset")
        with pytest.raises(ValidationError) as exc_info:
            process_value(spec, ["a", "b"])
        assert "single value" in (exc_info.value.detail or "")


# ---------------------------------------------------------------------------
# unknown type
# ---------------------------------------------------------------------------
class TestDispatchUnknown:
    def test_passthrough(self) -> None:
        spec = make_param_spec(name="p", param_type="unknown_type")
        result = process_value(spec, {"complex": "data"})
        assert result.kind is ParamKind.UNKNOWN
        assert result.value == {"complex": "data"}


# ---------------------------------------------------------------------------
# None value handling
# ---------------------------------------------------------------------------
class TestDispatchNone:
    def test_none_with_allow_empty_returns_empty(self) -> None:
        spec = make_param_spec(name="p", param_type="string", allow_empty=True)
        result = process_value(spec, None)
        assert result.kind is ParamKind.EMPTY
        assert result.value == ""

    def test_none_without_allow_empty_raises(self) -> None:
        spec = make_param_spec(name="p", param_type="string", allow_empty=False)
        with pytest.raises(ValidationError) as exc_info:
            process_value(spec, None)
        assert "requires a value" in (exc_info.value.detail or "")
