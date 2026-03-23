"""Unit tests for strategy combine operations."""

import pytest

from veupath_chatbot.domain.strategy.ops import (
    BOOLEAN_OPERATOR_OPTIONS_DESC,
    DEFAULT_COMBINE_OPERATOR,
    ColocationParams,
    CombineOp,
    get_wdk_operator,
    parse_op,
)


class TestParseOp:
    """Tests for parse_op() alias resolution and normalization."""

    def test_exact_enum_values(self) -> None:
        assert parse_op("INTERSECT") == CombineOp.INTERSECT
        assert parse_op("UNION") == CombineOp.UNION
        assert parse_op("MINUS") == CombineOp.MINUS
        assert parse_op("RMINUS") == CombineOp.RMINUS
        assert parse_op("LONLY") == CombineOp.LONLY
        assert parse_op("RONLY") == CombineOp.RONLY
        assert parse_op("COLOCATE") == CombineOp.COLOCATE

    def test_case_insensitive(self) -> None:
        assert parse_op("intersect") == CombineOp.INTERSECT
        assert parse_op("Union") == CombineOp.UNION
        assert parse_op("minus") == CombineOp.MINUS

    def test_common_aliases(self) -> None:
        assert parse_op("AND") == CombineOp.INTERSECT
        assert parse_op("INTERSECTION") == CombineOp.INTERSECT
        assert parse_op("OR") == CombineOp.UNION
        assert parse_op("PLUS") == CombineOp.UNION
        assert parse_op("NOT") == CombineOp.MINUS

    def test_directional_aliases(self) -> None:
        assert parse_op("LEFT_MINUS") == CombineOp.MINUS
        assert parse_op("RIGHT_MINUS") == CombineOp.RMINUS
        assert parse_op("LMINUS") == CombineOp.MINUS
        assert parse_op("MINUS_LEFT") == CombineOp.MINUS
        assert parse_op("MINUS_RIGHT") == CombineOp.RMINUS

    def test_hyphen_and_space_normalization(self) -> None:
        assert parse_op("left-minus") == CombineOp.MINUS
        assert parse_op("right minus") == CombineOp.RMINUS
        assert parse_op("minus-left") == CombineOp.MINUS

    def test_whitespace_stripped(self) -> None:
        assert parse_op("  INTERSECT  ") == CombineOp.INTERSECT

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="<empty>"):
            parse_op("")

    def test_none_like_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="<empty>"):
            parse_op("   ")

    def test_unknown_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown operator"):
            parse_op("BOGUS")


class TestGetWdkOperator:
    """Tests for get_wdk_operator()."""

    def test_returns_value_for_boolean_ops(self) -> None:
        assert get_wdk_operator(CombineOp.INTERSECT) == "INTERSECT"
        assert get_wdk_operator(CombineOp.UNION) == "UNION"
        assert get_wdk_operator(CombineOp.MINUS) == "MINUS"
        assert get_wdk_operator(CombineOp.RMINUS) == "RMINUS"
        assert get_wdk_operator(CombineOp.LONLY) == "LONLY"
        assert get_wdk_operator(CombineOp.RONLY) == "RONLY"

    def test_colocate_raises(self) -> None:
        with pytest.raises(ValueError, match="COLOCATE"):
            get_wdk_operator(CombineOp.COLOCATE)


class TestColocationParamsValidate:
    """Tests for ColocationParams.check_errors()."""

    def test_valid_defaults(self) -> None:
        params = ColocationParams()
        assert params.check_errors() == []

    def test_valid_custom(self) -> None:
        params = ColocationParams(upstream=1000, downstream=500, strand="same")
        assert params.check_errors() == []

    def test_negative_upstream(self) -> None:
        params = ColocationParams(upstream=-1)
        errors = params.check_errors()
        assert len(errors) == 1
        assert "Upstream" in errors[0]

    def test_negative_downstream(self) -> None:
        params = ColocationParams(downstream=-5)
        errors = params.check_errors()
        assert len(errors) == 1
        assert "Downstream" in errors[0]

    def test_both_negative(self) -> None:
        params = ColocationParams(upstream=-1, downstream=-2)
        errors = params.check_errors()
        assert len(errors) == 2

    def test_invalid_strand_coerces_to_both(self) -> None:
        """Invalid strand values are coerced to 'both' by the model validator."""
        params = ColocationParams(strand="invalid")
        assert params.strand == "both"

    def test_opposite_strand_valid(self) -> None:
        params = ColocationParams(strand="opposite")
        assert params.check_errors() == []

    def test_zero_distances_valid(self) -> None:
        params = ColocationParams(upstream=0, downstream=0)
        assert params.check_errors() == []


class TestModuleConstants:
    """Tests for module-level constants."""

    def test_default_combine_operator_is_intersect(self) -> None:
        assert DEFAULT_COMBINE_OPERATOR == CombineOp.INTERSECT

    def test_boolean_operator_options_desc(self) -> None:
        assert "INTERSECT" in BOOLEAN_OPERATOR_OPTIONS_DESC
        assert "UNION" in BOOLEAN_OPERATOR_OPTIONS_DESC
        assert "MINUS" in BOOLEAN_OPERATOR_OPTIONS_DESC

    def test_combine_op_is_str_enum(self) -> None:
        assert CombineOp.INTERSECT == "INTERSECT"
        assert str(CombineOp.UNION) == "UNION"


class TestParseOpFallback:
    """Test the CombineOp(norm) fallback path in parse_op."""

    def test_enum_value_fallback(self) -> None:
        # These go through the alias dict, but verify fallback path works too
        # by using exact values not in alias dict
        # All known values are in the alias dict, so the fallback only triggers
        # for values not in aliases. Since all enum values ARE in aliases,
        # the fallback is only reachable for values that happen to match
        # after normalization but aren't aliased. Let's verify the error
        # message for truly unknown values.
        with pytest.raises(ValueError, match="Unknown operator: xyz"):
            parse_op("xyz")
