"""Tests for combine operations (domain/strategy/ops.py).

Verifies parse_op() alias resolution, CombineOp enum, ColocationParams,
and get_wdk_operator().
"""

import pytest
from pydantic import ValidationError

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
    def test_defaults(self) -> None:
        params = ColocationParams()
        assert params.operation == "overlaps"
        assert params.strand == "either strand"
        assert params.output == "a"
        assert params.region_a == "exact"
        assert params.begin_a == "start"
        assert params.begin_direction_a == "+"
        assert params.begin_offset_a == 0
        assert params.end_a == "stop"
        assert params.end_direction_a == "+"
        assert params.end_offset_a == 0
        assert params.region_b == "exact"
        assert params.begin_offset_b == 0
        assert params.end_offset_b == 0

    def test_custom_regions(self) -> None:
        params = ColocationParams(
            region_a="upstream",
            begin_offset_a=1000,
            end_offset_a=500,
            region_b="downstream",
        )
        assert params.region_a == "upstream"
        assert params.begin_offset_a == 1000
        assert params.end_offset_a == 500
        assert params.region_b == "downstream"

    def test_all_operations(self) -> None:
        for op in ("overlaps", "contains", "is contained in"):
            params = ColocationParams(operation=op)
            assert params.operation == op

    def test_all_strands(self) -> None:
        for strand in ("either strand", "same strand", "opposite strand"):
            params = ColocationParams(strand=strand)
            assert params.strand == strand

    def test_negative_offset_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ColocationParams(begin_offset_a=-1)

    def test_negative_end_offset_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ColocationParams(end_offset_b=-1)

    def test_invalid_operation_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ColocationParams(operation="invalid")

    def test_invalid_strand_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ColocationParams(strand="both")

    def test_model_validate_from_dict(self) -> None:
        params = ColocationParams.model_validate(
            {"operation": "contains", "strand": "same strand"}
        )
        assert params.operation == "contains"
        assert params.strand == "same strand"

    def test_to_wdk_params_operation(self) -> None:
        assert ColocationParams(operation="overlaps").to_wdk_params()["span_operation"] == "overlap"
        assert ColocationParams(operation="contains").to_wdk_params()["span_operation"] == "a_contain_b"
        assert ColocationParams(operation="is contained in").to_wdk_params()["span_operation"] == "b_contain_a"

    def test_to_wdk_params_strand(self) -> None:
        assert ColocationParams(strand="either strand").to_wdk_params()["span_strand"] == "Both strands"
        assert ColocationParams(strand="same strand").to_wdk_params()["span_strand"] == "same strand"
        assert ColocationParams(strand="opposite strand").to_wdk_params()["span_strand"] == "opposite strand"

    def test_to_wdk_params_regions(self) -> None:
        params = ColocationParams(region_a="upstream", region_b="downstream")
        wdk = params.to_wdk_params()
        assert wdk["region_a"] == "upstream"
        assert wdk["region_b"] == "downstream"

    def test_to_wdk_params_offsets_as_strings(self) -> None:
        params = ColocationParams(begin_offset_a=1000, end_offset_b=500)
        wdk = params.to_wdk_params()
        assert wdk["span_begin_offset_a"] == "1000"
        assert wdk["span_end_offset_b"] == "500"

    def test_to_wdk_params_output(self) -> None:
        assert ColocationParams(output="a").to_wdk_params()["span_output"] == "a"
        assert ColocationParams(output="b").to_wdk_params()["span_output"] == "b"
