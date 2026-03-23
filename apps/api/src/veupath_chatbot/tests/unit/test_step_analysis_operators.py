"""Unit tests for step_analysis.phase_operators -- COMPARISON_OPERATORS constant."""

from veupath_chatbot.domain.strategy.ops import CombineOp
from veupath_chatbot.services.experiment.step_analysis.phase_operators import (
    COMPARISON_OPERATORS,
)


class TestComparisonOperators:
    def test_excludes_colocate(self) -> None:
        assert CombineOp.COLOCATE not in COMPARISON_OPERATORS

    def test_excludes_lonly(self) -> None:
        assert CombineOp.LONLY not in COMPARISON_OPERATORS

    def test_excludes_ronly(self) -> None:
        assert CombineOp.RONLY not in COMPARISON_OPERATORS

    def test_includes_intersect(self) -> None:
        assert CombineOp.INTERSECT in COMPARISON_OPERATORS

    def test_includes_union(self) -> None:
        assert CombineOp.UNION in COMPARISON_OPERATORS

    def test_includes_minus(self) -> None:
        assert CombineOp.MINUS in COMPARISON_OPERATORS

    def test_includes_rminus(self) -> None:
        assert CombineOp.RMINUS in COMPARISON_OPERATORS

    def test_no_duplicates(self) -> None:
        assert len(COMPARISON_OPERATORS) == len(set(COMPARISON_OPERATORS))
