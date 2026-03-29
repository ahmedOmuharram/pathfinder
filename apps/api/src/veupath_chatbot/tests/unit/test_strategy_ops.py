"""Unit tests for strategy combine operations."""

import pytest
from pydantic import ValidationError

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
    """Tests for ColocationParams Pydantic validation (Field(ge=0) and Literal)."""

    def test_valid_defaults(self) -> None:
        params = ColocationParams()
        assert params.operation == "overlaps"
        assert params.strand == "either strand"
        assert params.begin_offset_a == 0
        assert params.end_offset_a == 0

    def test_valid_custom(self) -> None:
        params = ColocationParams(
            operation="contains",
            strand="same strand",
            region_a="upstream",
            begin_offset_a=1000,
            end_offset_a=500,
        )
        assert params.operation == "contains"
        assert params.strand == "same strand"
        assert params.begin_offset_a == 1000

    def test_negative_begin_offset_a_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ColocationParams(begin_offset_a=-1)

    def test_negative_end_offset_a_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ColocationParams(end_offset_a=-5)

    def test_negative_begin_offset_b_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ColocationParams(begin_offset_b=-1)

    def test_negative_end_offset_b_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ColocationParams(end_offset_b=-2)

    def test_invalid_strand_rejected(self) -> None:
        """Invalid strand values are rejected by Pydantic Literal validation."""
        with pytest.raises(ValidationError):
            ColocationParams(strand="invalid")

    def test_opposite_strand_valid(self) -> None:
        params = ColocationParams(strand="opposite strand")
        assert params.strand == "opposite strand"

    def test_zero_offsets_valid(self) -> None:
        params = ColocationParams(begin_offset_a=0, end_offset_a=0)
        assert params.begin_offset_a == 0
        assert params.end_offset_a == 0


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
