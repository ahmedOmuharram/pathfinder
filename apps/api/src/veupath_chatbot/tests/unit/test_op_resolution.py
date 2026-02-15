"""Tests for operation parsing and resolution."""

import pytest

from veupath_chatbot.domain.strategy.ops import (
    CombineOp,
    get_op_label,
    get_wdk_operator,
    parse_op,
)


class TestOperationParsing:
    """Tests for operation parsing."""

    def test_parse_standard_operators(self) -> None:
        """Test parsing standard operator names."""
        assert parse_op("INTERSECT") == CombineOp.INTERSECT
        assert parse_op("UNION") == CombineOp.UNION
        assert parse_op("MINUS_LEFT") == CombineOp.MINUS_LEFT
        assert parse_op("MINUS_RIGHT") == CombineOp.MINUS_RIGHT
        assert parse_op("COLOCATE") == CombineOp.COLOCATE

    def test_parse_case_insensitive(self) -> None:
        """Test that parsing is case insensitive."""
        assert parse_op("intersect") == CombineOp.INTERSECT
        assert parse_op("Union") == CombineOp.UNION
        assert parse_op("COLOCATE") == CombineOp.COLOCATE

    def test_parse_aliases(self) -> None:
        """Test parsing operator aliases."""
        assert parse_op("AND") == CombineOp.INTERSECT
        assert parse_op("OR") == CombineOp.UNION
        assert parse_op("MINUS") == CombineOp.MINUS_LEFT
        assert parse_op("NOT") == CombineOp.MINUS_LEFT

    def test_parse_wdk_operator_values(self) -> None:
        """Test parsing the exact values WDK stores in bq_operator.

        These come from the WDK BooleanOperator Java enum's getBaseOperator():
        UNION, INTERSECT, MINUS (left), RMINUS (right), LONLY, RONLY.


        """
        assert parse_op("INTERSECT") == CombineOp.INTERSECT
        assert parse_op("UNION") == CombineOp.UNION
        assert parse_op("MINUS") == CombineOp.MINUS_LEFT
        assert parse_op("RMINUS") == CombineOp.MINUS_RIGHT
        assert parse_op("LMINUS") == CombineOp.MINUS_LEFT
        assert parse_op("LONLY") == CombineOp.MINUS_LEFT
        assert parse_op("RONLY") == CombineOp.MINUS_RIGHT

    def test_parse_with_separators(self) -> None:
        """Test parsing with different separators."""
        assert parse_op("MINUS-LEFT") == CombineOp.MINUS_LEFT
        assert parse_op("MINUS LEFT") == CombineOp.MINUS_LEFT
        assert parse_op("LEFT_MINUS") == CombineOp.MINUS_LEFT

    def test_parse_invalid_raises(self) -> None:
        """Test that invalid operators raise ValueError."""
        with pytest.raises(ValueError):
            parse_op("INVALID_OP")

    def test_parse_empty_raises(self) -> None:
        """Test that empty / whitespace-only operators raise ValueError."""
        with pytest.raises(ValueError):
            parse_op("")
        with pytest.raises(ValueError):
            parse_op("   ")

    def test_get_op_labels(self) -> None:
        """Test getting human-readable labels."""
        assert "AND" in get_op_label(CombineOp.INTERSECT)
        assert "OR" in get_op_label(CombineOp.UNION)

    def test_get_wdk_operators(self) -> None:
        """Test getting WDK boolean operator names."""
        assert get_wdk_operator(CombineOp.INTERSECT) == "INTERSECT"
        assert get_wdk_operator(CombineOp.UNION) == "UNION"
        assert get_wdk_operator(CombineOp.MINUS_LEFT) == "MINUS"
        assert get_wdk_operator(CombineOp.MINUS_RIGHT) == "RMINUS"

    def test_colocate_not_boolean(self) -> None:
        """Test that COLOCATE raises when treated as boolean op."""
        with pytest.raises(ValueError):
            get_wdk_operator(CombineOp.COLOCATE)
