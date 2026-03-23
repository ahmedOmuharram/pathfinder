"""Tests for parameter normalization (domain/parameters/normalize.py).

Verifies ParameterNormalizer produces correct WDK wire format:
- Multi-pick lists → JSON strings
- Ranges → JSON strings
- Filters → JSON strings
- Scalars → strings
- Unknown params → ValidationError
- input-step params → skipped
"""

import json

import pytest

from veupath_chatbot.domain.parameters.normalize import ParameterNormalizer
from veupath_chatbot.domain.parameters.specs import ParamSpecNormalized
from veupath_chatbot.platform.errors import ValidationError


def _make_normalizer(specs: dict[str, ParamSpecNormalized]) -> ParameterNormalizer:
    return ParameterNormalizer(specs=specs)


def _spec(name: str, param_type: str, **kwargs: object) -> ParamSpecNormalized:
    field_map = {"allow_empty": "allow_empty_value"}
    mapped = {field_map.get(k, k): v for k, v in kwargs.items()}
    return ParamSpecNormalized(name=name, param_type=param_type, **mapped)


class TestMultiPick:
    def test_list_becomes_json_string(self) -> None:
        """Multi-pick values must be JSON-encoded strings on the wire."""
        normalizer = _make_normalizer(
            {"org": _spec("org", "multi-pick-vocabulary", allow_empty=True)}
        )
        result = normalizer.normalize({"org": ["pfal", "pviv"]})
        # Wire format is JSON string
        assert result["org"] == '["pfal", "pviv"]'
        # Verify it's valid JSON
        assert json.loads(result["org"]) == ["pfal", "pviv"]

    def test_json_string_decoded_and_re_encoded(self) -> None:
        """Already-JSON string input should be decoded then re-encoded."""
        normalizer = _make_normalizer(
            {"org": _spec("org", "multi-pick-vocabulary", allow_empty=True)}
        )
        result = normalizer.normalize({"org": '["pfal"]'})
        assert json.loads(result["org"]) == ["pfal"]

    def test_empty_list_allowed(self) -> None:
        normalizer = _make_normalizer(
            {"org": _spec("org", "multi-pick-vocabulary", allow_empty=True)}
        )
        result = normalizer.normalize({"org": []})
        assert result["org"] == "[]"


class TestScalar:
    def test_string_value(self) -> None:
        normalizer = _make_normalizer({"q": _spec("q", "string", allow_empty=True)})
        result = normalizer.normalize({"q": "kinase"})
        assert result["q"] == "kinase"

    def test_number_value(self) -> None:
        normalizer = _make_normalizer(
            {"threshold": _spec("threshold", "number", allow_empty=True)}
        )
        result = normalizer.normalize({"threshold": 0.5})
        assert result["threshold"] == "0.5"

    def test_bool_value(self) -> None:
        normalizer = _make_normalizer(
            {"flag": _spec("flag", "string", allow_empty=True)}
        )
        result = normalizer.normalize({"flag": True})
        assert result["flag"] == "true"

    def test_date_value(self) -> None:
        normalizer = _make_normalizer(
            {"start": _spec("start", "date", allow_empty=True)}
        )
        result = normalizer.normalize({"start": "2024-01-01"})
        assert result["start"] == "2024-01-01"

    def test_numeric_range_validation_rejects_below_min(self) -> None:
        normalizer = _make_normalizer(
            {"x": _spec("x", "number", min_value=0, max_value=100)}
        )
        with pytest.raises(ValidationError, match="below minimum"):
            normalizer.normalize({"x": -1})

    def test_numeric_range_validation_rejects_above_max(self) -> None:
        normalizer = _make_normalizer(
            {"x": _spec("x", "number", min_value=0, max_value=100)}
        )
        with pytest.raises(ValidationError, match="exceeds maximum"):
            normalizer.normalize({"x": 101})

    def test_is_number_string_param_validates_range(self) -> None:
        """StringParam with isNumber=True should validate numeric range."""
        normalizer = _make_normalizer(
            {
                "threshold": _spec(
                    "threshold", "string", is_number=True, min_value=0, max_value=1
                )
            }
        )
        with pytest.raises(ValidationError, match="exceeds maximum"):
            normalizer.normalize({"threshold": 1.5})

    def test_string_length_validation(self) -> None:
        normalizer = _make_normalizer({"q": _spec("q", "string", max_length=5)})
        with pytest.raises(ValidationError, match="maximum length"):
            normalizer.normalize({"q": "toolong"})

    def test_list_value_for_scalar_raises(self) -> None:
        normalizer = _make_normalizer({"q": _spec("q", "string", allow_empty=True)})
        with pytest.raises(ValidationError, match="scalar"):
            normalizer.normalize({"q": [1, 2, 3]})


class TestRange:
    def test_dict_range_becomes_json_string(self) -> None:
        normalizer = _make_normalizer(
            {"r": _spec("r", "number-range", allow_empty=True)}
        )
        result = normalizer.normalize({"r": {"min": 0, "max": 100}})
        parsed = json.loads(result["r"])
        assert parsed["min"] == 0
        assert parsed["max"] == 100

    def test_list_pair_becomes_range(self) -> None:
        normalizer = _make_normalizer(
            {"r": _spec("r", "number-range", allow_empty=True)}
        )
        result = normalizer.normalize({"r": [0, 100]})
        parsed = json.loads(result["r"])
        assert parsed["min"] == 0
        assert parsed["max"] == 100

    def test_date_range(self) -> None:
        normalizer = _make_normalizer({"d": _spec("d", "date-range", allow_empty=True)})
        result = normalizer.normalize({"d": {"min": "2024-01-01", "max": "2024-12-31"}})
        parsed = json.loads(result["d"])
        assert parsed["min"] == "2024-01-01"

    def test_invalid_range_raises(self) -> None:
        normalizer = _make_normalizer(
            {"r": _spec("r", "number-range", allow_empty=True)}
        )
        with pytest.raises(ValidationError, match="range"):
            normalizer.normalize({"r": "not a range"})


class TestFilter:
    def test_dict_filter_becomes_json_string(self) -> None:
        normalizer = _make_normalizer({"f": _spec("f", "filter", allow_empty=True)})
        result = normalizer.normalize({"f": {"values": ["a", "b"]}})
        parsed = json.loads(result["f"])
        assert parsed["values"] == ["a", "b"]

    def test_list_filter_becomes_json_string(self) -> None:
        normalizer = _make_normalizer({"f": _spec("f", "filter", allow_empty=True)})
        result = normalizer.normalize({"f": [{"name": "x", "value": "y"}]})
        parsed = json.loads(result["f"])
        assert len(parsed) == 1

    def test_string_filter_passes_through(self) -> None:
        normalizer = _make_normalizer({"f": _spec("f", "filter", allow_empty=True)})
        result = normalizer.normalize({"f": "raw_string"})
        assert result["f"] == "raw_string"


class TestInputStep:
    def test_input_step_skipped(self) -> None:
        """input-step params should be silently skipped."""
        normalizer = _make_normalizer(
            {
                "bq_input_step": _spec("bq_input_step", "input-step"),
                "bq_operator": _spec("bq_operator", "string", allow_empty=True),
            }
        )
        result = normalizer.normalize(
            {"bq_input_step": "123", "bq_operator": "INTERSECT"}
        )
        assert "bq_input_step" not in result
        assert result["bq_operator"] == "INTERSECT"


class TestUnknownParam:
    def test_unknown_param_raises(self) -> None:
        normalizer = _make_normalizer(
            {"known": _spec("known", "string", allow_empty=True)}
        )
        with pytest.raises(ValidationError, match="does not exist"):
            normalizer.normalize({"unknown_param": "value"})

    def test_error_lists_available_params(self) -> None:
        normalizer = _make_normalizer(
            {
                "alpha": _spec("alpha", "string", allow_empty=True),
                "beta": _spec("beta", "string", allow_empty=True),
            }
        )
        with pytest.raises(ValidationError, match="alpha") as exc_info:
            normalizer.normalize({"gamma": "value"})
        assert "beta" in str(exc_info.value)


class TestNoneHandling:
    def test_none_value_for_allow_empty(self) -> None:
        normalizer = _make_normalizer({"q": _spec("q", "string", allow_empty=True)})
        result = normalizer.normalize({"q": None})
        assert result["q"] == ""

    def test_none_value_for_required_raises(self) -> None:
        normalizer = _make_normalizer({"q": _spec("q", "string", allow_empty=False)})
        with pytest.raises(ValidationError, match="requires a value"):
            normalizer.normalize({"q": None})

    def test_none_parameters_returns_empty(self) -> None:
        normalizer = _make_normalizer({"q": _spec("q", "string", allow_empty=True)})
        result = normalizer.normalize(None)
        assert result == {}

    def test_empty_parameters(self) -> None:
        normalizer = _make_normalizer({"q": _spec("q", "string", allow_empty=True)})
        result = normalizer.normalize({})
        assert result == {}
