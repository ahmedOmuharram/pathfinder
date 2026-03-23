"""Tests for combine operations (domain/strategy/ops.py).

Verifies parse_op() alias resolution, CombineOp enum, ColocationParams,
and get_wdk_operator().
"""

import pytest

from veupath_chatbot.domain.strategy.ops import (
    ColocationParams,
    CombineOp,
    get_wdk_operator,
    parse_op,
)


class TestParseOp:
    """Tests for parse_op() — operator string parsing with aliases."""

    def test_canonical_values(self) -> None:
        assert parse_op("INTERSECT") == CombineOp.INTERSECT
        assert parse_op("UNION") == CombineOp.UNION
        assert parse_op("MINUS") == CombineOp.MINUS
        assert parse_op("RMINUS") == CombineOp.RMINUS
        assert parse_op("LONLY") == CombineOp.LONLY
        assert parse_op("RONLY") == CombineOp.RONLY
        assert parse_op("COLOCATE") == CombineOp.COLOCATE

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

    def test_case_insensitive(self) -> None:
        assert parse_op("intersect") == CombineOp.INTERSECT
        assert parse_op("Union") == CombineOp.UNION
        assert parse_op("minus") == CombineOp.MINUS

    def test_hyphen_to_underscore(self) -> None:
        """Hyphens should be normalized to underscores."""
        assert parse_op("LEFT-MINUS") == CombineOp.MINUS
        assert parse_op("RIGHT-MINUS") == CombineOp.RMINUS

    def test_space_to_underscore(self) -> None:
        assert parse_op("LEFT MINUS") == CombineOp.MINUS
        assert parse_op("MINUS RIGHT") == CombineOp.RMINUS

    def test_whitespace_stripped(self) -> None:
        assert parse_op("  INTERSECT  ") == CombineOp.INTERSECT

    def test_empty_string_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            parse_op("")

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            parse_op("   ")

    def test_unknown_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown operator"):
            parse_op("XYZZY")


class TestGetWdkOperator:
    def test_intersect(self) -> None:
        assert get_wdk_operator(CombineOp.INTERSECT) == "INTERSECT"

    def test_union(self) -> None:
        assert get_wdk_operator(CombineOp.UNION) == "UNION"

    def test_minus(self) -> None:
        assert get_wdk_operator(CombineOp.MINUS) == "MINUS"

    def test_colocate_raises(self) -> None:
        """COLOCATE is not a boolean operator — requires special handling."""
        with pytest.raises(ValueError, match="COLOCATE"):
            get_wdk_operator(CombineOp.COLOCATE)


class TestCombineOpEnum:
    def test_all_values_uppercase(self) -> None:
        for op in CombineOp:
            assert op.value == op.value.upper()

    def test_seven_operators(self) -> None:
        assert len(CombineOp) == 7

    def test_str_enum(self) -> None:
        """CombineOp is a StrEnum — can be used as string."""
        assert str(CombineOp.INTERSECT) == "INTERSECT"


class TestColocationParams:
    def test_from_raw_colocate(self) -> None:
        result = ColocationParams.from_raw(
            CombineOp.COLOCATE, upstream=1000, downstream=500, strand="same"
        )
        assert result is not None
        assert result.upstream == 1000
        assert result.downstream == 500
        assert result.strand == "same"

    def test_from_raw_non_colocate_returns_none(self) -> None:
        result = ColocationParams.from_raw(
            CombineOp.INTERSECT, upstream=1000, downstream=500, strand="same"
        )
        assert result is None

    def test_from_raw_none_operator_returns_none(self) -> None:
        result = ColocationParams.from_raw(
            None, upstream=1000, downstream=500, strand="same"
        )
        assert result is None

    def test_from_raw_defaults(self) -> None:
        result = ColocationParams.from_raw(
            CombineOp.COLOCATE, upstream=None, downstream=None, strand=None
        )
        assert result is not None
        assert result.upstream == 0
        assert result.downstream == 0
        assert result.strand == "both"

    def test_from_raw_invalid_strand(self) -> None:
        result = ColocationParams.from_raw(
            CombineOp.COLOCATE, upstream=0, downstream=0, strand="invalid"
        )
        assert result is not None
        assert result.strand == "both"

    def test_check_errors_valid(self) -> None:
        params = ColocationParams(upstream=1000, downstream=500, strand="same")
        assert params.check_errors() == []

    def test_check_errors_negative_upstream(self) -> None:
        params = ColocationParams(upstream=-1, downstream=500, strand="same")
        errors = params.check_errors()
        assert any("Upstream" in e for e in errors)

    def test_check_errors_negative_downstream(self) -> None:
        params = ColocationParams(upstream=0, downstream=-1, strand="same")
        errors = params.check_errors()
        assert any("Downstream" in e for e in errors)
