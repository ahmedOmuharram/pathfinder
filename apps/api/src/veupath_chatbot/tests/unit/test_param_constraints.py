"""Tests for numeric/string constraint validation on parameters.

Covers:
- ParamSpecNormalized.from_wdk reading min/max/increment/maxLength from WDK params
- normalize raising for out-of-range numeric values
- normalize accepting in-range numeric values
- canonicalize raising for out-of-range numeric values
- boundary values (exactly min, exactly max)
- string length validation
"""

import pytest

from veupath_chatbot.domain.parameters.canonicalize import ParameterCanonicalizer
from veupath_chatbot.domain.parameters.normalize import ParameterNormalizer
from veupath_chatbot.domain.parameters.specs import (
    ParamSpecNormalized,
)
from veupath_chatbot.integrations.veupathdb.wdk_parameters import (
    WDKNumberParam,
    WDKStringParam,
)
from veupath_chatbot.platform.errors import ValidationError
from veupath_chatbot.tests.fixtures.builders import ParamSpecConfig, make_param_spec


def _assert_validation_error(
    exc_info: pytest.ExceptionInfo[ValidationError], pattern: str
) -> None:
    """Assert that a ValidationError's detail contains the expected pattern."""
    assert exc_info.value.detail is not None
    assert pattern in exc_info.value.detail


# ---------------------------------------------------------------------------
# ParamSpecNormalized.from_wdk: reading constraint fields from typed WDK params
# ---------------------------------------------------------------------------


class TestFromWdkConstraints:
    """Test that ParamSpecNormalized.from_wdk reads constraint fields from typed WDK params."""

    def test_reads_min_max(self) -> None:
        param = WDKNumberParam(name="score", min=0, max=100)
        spec = ParamSpecNormalized.from_wdk(param)
        assert spec.min_value == 0.0
        assert spec.max_value == 100.0

    def test_reads_float_min_max(self) -> None:
        param = WDKNumberParam(name="pvalue", min=0.0, max=1.0)
        spec = ParamSpecNormalized.from_wdk(param)
        assert spec.min_value == 0.0
        assert spec.max_value == 1.0

    def test_reads_increment(self) -> None:
        param = WDKNumberParam(name="score", increment=0.5)
        spec = ParamSpecNormalized.from_wdk(param)
        assert spec.increment == 0.5

    def test_reads_max_length(self) -> None:
        param = WDKStringParam(name="keyword", length=200)
        spec = ParamSpecNormalized.from_wdk(param)
        assert spec.max_length == 200

    def test_defaults_to_none_when_not_present(self) -> None:
        param = WDKStringParam(name="keyword")
        spec = ParamSpecNormalized.from_wdk(param)
        assert spec.min_value is None
        assert spec.max_value is None
        assert spec.increment is None
        # WDKStringParam defaults length=0, which from_wdk converts to None
        assert spec.max_length is None


# ---------------------------------------------------------------------------
# Normalize: numeric range validation
# ---------------------------------------------------------------------------


class TestNormalizeNumericConstraints:
    """Test that normalize raises for out-of-range numeric values."""

    def _make_normalizer(self, spec: ParamSpecNormalized) -> ParameterNormalizer:
        return ParameterNormalizer(specs={spec.name: spec})

    def test_accepts_in_range_value(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(
                name="score", param_type="number", min_value=0, max_value=100
            )
        )
        normalizer = self._make_normalizer(spec)
        result = normalizer.normalize({"score": 50})
        assert result["score"] == "50"

    def test_accepts_boundary_min(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(
                name="score", param_type="number", min_value=0, max_value=100
            )
        )
        normalizer = self._make_normalizer(spec)
        result = normalizer.normalize({"score": 0})
        assert result["score"] == "0"

    def test_accepts_boundary_max(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(
                name="score", param_type="number", min_value=0, max_value=100
            )
        )
        normalizer = self._make_normalizer(spec)
        result = normalizer.normalize({"score": 100})
        assert result["score"] == "100"

    def test_rejects_below_min(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(
                name="score", param_type="number", min_value=0, max_value=100
            )
        )
        normalizer = self._make_normalizer(spec)
        with pytest.raises(ValidationError) as exc_info:
            normalizer.normalize({"score": -1})
        _assert_validation_error(exc_info, "below minimum")

    def test_rejects_above_max(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(
                name="score", param_type="number", min_value=0, max_value=100
            )
        )
        normalizer = self._make_normalizer(spec)
        with pytest.raises(ValidationError) as exc_info:
            normalizer.normalize({"score": 101})
        _assert_validation_error(exc_info, "exceeds maximum")

    def test_no_constraint_allows_any_value(self) -> None:
        spec = make_param_spec(ParamSpecConfig(name="score", param_type="number"))
        normalizer = self._make_normalizer(spec)
        result = normalizer.normalize({"score": 999999})
        assert result["score"] == "999999"

    def test_only_min_constraint(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(name="score", param_type="number", min_value=10)
        )
        normalizer = self._make_normalizer(spec)
        result = normalizer.normalize({"score": 999999})
        assert result["score"] == "999999"
        with pytest.raises(ValidationError) as exc_info:
            normalizer.normalize({"score": 5})
        _assert_validation_error(exc_info, "below minimum")

    def test_only_max_constraint(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(name="score", param_type="number", max_value=100)
        )
        normalizer = self._make_normalizer(spec)
        result = normalizer.normalize({"score": -999})
        assert result["score"] == "-999"
        with pytest.raises(ValidationError) as exc_info:
            normalizer.normalize({"score": 101})
        _assert_validation_error(exc_info, "exceeds maximum")

    def test_string_numeric_value_validated(self) -> None:
        """Values passed as strings should still be range-checked."""
        spec = make_param_spec(
            ParamSpecConfig(
                name="score", param_type="number", min_value=0, max_value=100
            )
        )
        normalizer = self._make_normalizer(spec)
        result = normalizer.normalize({"score": "50"})
        assert result["score"] == "50"
        with pytest.raises(ValidationError) as exc_info:
            normalizer.normalize({"score": "-1"})
        _assert_validation_error(exc_info, "below minimum")

    def test_non_numeric_string_skips_range_check(self) -> None:
        """Non-numeric strings should not trigger range validation."""
        spec = make_param_spec(
            ParamSpecConfig(
                name="keyword", param_type="string", min_value=0, max_value=100
            )
        )
        normalizer = self._make_normalizer(spec)
        result = normalizer.normalize({"keyword": "hello"})
        assert result["keyword"] == "hello"

    def test_number_range_param_validated(self) -> None:
        """Number-range params should have both min and max validated."""
        spec = make_param_spec(
            ParamSpecConfig(
                name="range_param",
                param_type="number-range",
                min_value=0,
                max_value=100,
            )
        )
        normalizer = self._make_normalizer(spec)
        result = normalizer.normalize({"range_param": {"min": 10, "max": 90}})
        assert result["range_param"] == '{"min": 10, "max": 90}'

    def test_number_range_param_rejects_below_min(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(
                name="range_param",
                param_type="number-range",
                min_value=0,
                max_value=100,
            )
        )
        normalizer = self._make_normalizer(spec)
        with pytest.raises(ValidationError) as exc_info:
            normalizer.normalize({"range_param": {"min": -5, "max": 50}})
        _assert_validation_error(exc_info, "below minimum")

    def test_number_range_param_rejects_above_max(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(
                name="range_param",
                param_type="number-range",
                min_value=0,
                max_value=100,
            )
        )
        normalizer = self._make_normalizer(spec)
        with pytest.raises(ValidationError) as exc_info:
            normalizer.normalize({"range_param": {"min": 10, "max": 150}})
        _assert_validation_error(exc_info, "exceeds maximum")


# ---------------------------------------------------------------------------
# Normalize: string length validation
# ---------------------------------------------------------------------------


class TestNumberParamMaxLengthZero:
    """Regression: WDK emits maxLength=0 for number params (meaning no limit).

    fold_change (type=number, maxLength=0) must NOT reject value "2".
    """

    def test_number_param_with_max_length_zero_accepts_value(self) -> None:
        """The exact bug: fold_change=2 rejected by max_length=0."""
        spec = make_param_spec(
            ParamSpecConfig(name="fold_change", param_type="number", max_length=0)
        )
        normalizer = ParameterNormalizer(specs={spec.name: spec})
        result = normalizer.normalize({"fold_change": "2"})
        assert result["fold_change"] == "2"

    def test_from_wdk_treats_length_zero_as_none(self) -> None:
        """WDK StringParam length=0 should be treated as no limit (None)."""
        param = WDKStringParam(name="fold_change", length=0)
        spec = ParamSpecNormalized.from_wdk(param)
        assert spec.max_length is None

    def test_string_length_check_skipped_for_number_type(self) -> None:
        """Even if max_length is somehow set on a number param, don't check it."""
        spec = make_param_spec(
            ParamSpecConfig(name="fold_change", param_type="number", max_length=1)
        )
        normalizer = ParameterNormalizer(specs={spec.name: spec})
        # "20" is 2 chars, exceeds max_length=1, but it's a number param
        result = normalizer.normalize({"fold_change": "20"})
        assert result["fold_change"] == "20"

    def test_string_param_max_length_still_enforced(self) -> None:
        """String params should still enforce max_length."""
        spec = make_param_spec(
            ParamSpecConfig(name="keyword", param_type="string", max_length=3)
        )
        normalizer = ParameterNormalizer(specs={spec.name: spec})
        with pytest.raises(ValidationError):
            normalizer.normalize({"keyword": "hello"})


class TestIsNumberStringParam:
    """WDK StringParam with isNumber=true (e.g. fold_change).

    WDK emits type="string" + isNumber=true for params like fold_change.
    These should get numeric range validation even though their type is string.
    """

    def test_from_wdk_reads_is_number_true(self) -> None:
        param = WDKStringParam(name="fold_change", is_number=True, length=0)
        spec = ParamSpecNormalized.from_wdk(param)
        assert spec.is_number is True
        assert spec.param_type == "string"

    def test_from_wdk_reads_is_number_false(self) -> None:
        param = WDKStringParam(name="keyword", is_number=False)
        spec = ParamSpecNormalized.from_wdk(param)
        assert spec.is_number is False

    def test_from_wdk_defaults_is_number_to_false(self) -> None:
        param = WDKStringParam(name="keyword")
        spec = ParamSpecNormalized.from_wdk(param)
        assert spec.is_number is False

    def test_string_is_number_gets_numeric_range_validation(self) -> None:
        """type=string + isNumber=true with min/max should enforce range."""
        spec = make_param_spec(
            ParamSpecConfig(
                name="fold_change",
                param_type="string",
                is_number=True,
                min_value=0,
                max_value=100,
            )
        )
        normalizer = ParameterNormalizer(specs={spec.name: spec})
        result = normalizer.normalize({"fold_change": "2"})
        assert result["fold_change"] == "2"

    def test_string_is_number_rejects_below_min(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(
                name="fold_change",
                param_type="string",
                is_number=True,
                min_value=1,
                max_value=100,
            )
        )
        normalizer = ParameterNormalizer(specs={spec.name: spec})
        with pytest.raises(ValidationError) as exc_info:
            normalizer.normalize({"fold_change": "0.5"})
        _assert_validation_error(exc_info, "below minimum")

    def test_string_is_number_rejects_above_max(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(
                name="fold_change",
                param_type="string",
                is_number=True,
                min_value=0,
                max_value=10,
            )
        )
        normalizer = ParameterNormalizer(specs={spec.name: spec})
        with pytest.raises(ValidationError) as exc_info:
            normalizer.normalize({"fold_change": "20"})
        _assert_validation_error(exc_info, "exceeds maximum")

    def test_string_not_is_number_skips_range_check(self) -> None:
        """Plain string params (isNumber=false) should not get range validation."""
        spec = make_param_spec(
            ParamSpecConfig(
                name="keyword",
                param_type="string",
                is_number=False,
                min_value=0,
                max_value=100,
            )
        )
        normalizer = ParameterNormalizer(specs={spec.name: spec})
        # "hello" is not numeric, should pass through without range error
        result = normalizer.normalize({"keyword": "hello"})
        assert result["keyword"] == "hello"

    def test_real_fold_change_scenario(self) -> None:
        """End-to-end: construct WDK param for fold_change, then normalize value."""
        param = WDKStringParam(
            name="fold_change",
            is_number=True,
            length=0,
            allow_empty_value=False,
            initial_display_value="2",
        )
        spec = ParamSpecNormalized.from_wdk(param)
        assert spec.param_type == "string"
        assert spec.is_number is True
        assert spec.max_length is None  # length=0 -> None

        normalizer = ParameterNormalizer(specs={spec.name: spec})
        result = normalizer.normalize({"fold_change": "2"})
        assert result["fold_change"] == "2"


class TestNormalizeStringConstraints:
    """Test that normalize validates string length."""

    def _make_normalizer(self, spec: ParamSpecNormalized) -> ParameterNormalizer:
        return ParameterNormalizer(specs={spec.name: spec})

    def test_accepts_within_max_length(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(name="keyword", param_type="string", max_length=10)
        )
        normalizer = self._make_normalizer(spec)
        result = normalizer.normalize({"keyword": "hello"})
        assert result["keyword"] == "hello"

    def test_accepts_exact_max_length(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(name="keyword", param_type="string", max_length=5)
        )
        normalizer = self._make_normalizer(spec)
        result = normalizer.normalize({"keyword": "hello"})
        assert result["keyword"] == "hello"

    def test_rejects_exceeding_max_length(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(name="keyword", param_type="string", max_length=3)
        )
        normalizer = self._make_normalizer(spec)
        with pytest.raises(ValidationError) as exc_info:
            normalizer.normalize({"keyword": "hello"})
        _assert_validation_error(exc_info, "exceeds maximum length")

    def test_no_max_length_allows_any_length(self) -> None:
        spec = make_param_spec(ParamSpecConfig(name="keyword", param_type="string"))
        normalizer = self._make_normalizer(spec)
        result = normalizer.normalize({"keyword": "a" * 10000})
        assert result["keyword"] == "a" * 10000


# ---------------------------------------------------------------------------
# Canonicalize: numeric range validation
# ---------------------------------------------------------------------------


class TestCanonicalizeNumericConstraints:
    """Test that canonicalize raises for out-of-range numeric values."""

    def _make_canonicalizer(self, spec: ParamSpecNormalized) -> ParameterCanonicalizer:
        return ParameterCanonicalizer(specs={spec.name: spec})

    def test_accepts_in_range_value(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(
                name="score", param_type="number", min_value=0, max_value=100
            )
        )
        canon = self._make_canonicalizer(spec)
        result = canon.canonicalize({"score": 50})
        assert result["score"] == "50"

    def test_rejects_below_min(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(
                name="score", param_type="number", min_value=0, max_value=100
            )
        )
        canon = self._make_canonicalizer(spec)
        with pytest.raises(ValidationError) as exc_info:
            canon.canonicalize({"score": -1})
        _assert_validation_error(exc_info, "below minimum")

    def test_rejects_above_max(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(
                name="score", param_type="number", min_value=0, max_value=100
            )
        )
        canon = self._make_canonicalizer(spec)
        with pytest.raises(ValidationError) as exc_info:
            canon.canonicalize({"score": 101})
        _assert_validation_error(exc_info, "exceeds maximum")

    def test_accepts_boundary_values(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(
                name="score", param_type="number", min_value=0, max_value=100
            )
        )
        canon = self._make_canonicalizer(spec)
        result_min = canon.canonicalize({"score": 0})
        result_max = canon.canonicalize({"score": 100})
        assert result_min["score"] == "0"
        assert result_max["score"] == "100"


# ---------------------------------------------------------------------------
# Canonicalize: string length validation
# ---------------------------------------------------------------------------


class TestCanonicalizeStringConstraints:
    """Test that canonicalize validates string length."""

    def _make_canonicalizer(self, spec: ParamSpecNormalized) -> ParameterCanonicalizer:
        return ParameterCanonicalizer(specs={spec.name: spec})

    def test_rejects_exceeding_max_length(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(name="keyword", param_type="string", max_length=3)
        )
        canon = self._make_canonicalizer(spec)
        with pytest.raises(ValidationError) as exc_info:
            canon.canonicalize({"keyword": "hello"})
        _assert_validation_error(exc_info, "exceeds maximum length")

    def test_accepts_within_max_length(self) -> None:
        spec = make_param_spec(
            ParamSpecConfig(name="keyword", param_type="string", max_length=10)
        )
        canon = self._make_canonicalizer(spec)
        result = canon.canonicalize({"keyword": "hello"})
        assert result["keyword"] == "hello"
