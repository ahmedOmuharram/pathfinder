"""Tests for strategy DSL validation."""


from veupath_chatbot.domain.strategy.ast import (
    SearchStep,
    CombineStep,
    TransformStep,
    StrategyAST,
)
from veupath_chatbot.domain.strategy.ops import CombineOp
from veupath_chatbot.domain.strategy.validate import StrategyValidator, validate_strategy


class TestStrategyValidator:
    """Tests for StrategyValidator."""

    def test_validate_simple_search_strategy(self):
        """Test validation of a simple search strategy."""
        step = SearchStep(
            record_type="gene",
            search_name="GenesByGoTerm",
            parameters={"GoTerm": "GO:0016301"},
        )
        strategy = StrategyAST(record_type="gene", root=step)

        result = validate_strategy(strategy)
        assert result.valid
        assert len(result.errors) == 0

    def test_validate_missing_record_type(self):
        """Test validation fails when record type is missing."""
        step = SearchStep(
            record_type="gene",
            search_name="GenesByGoTerm",
            parameters={"GoTerm": "GO:0016301"},
        )
        strategy = StrategyAST(record_type="", root=step)

        result = validate_strategy(strategy)
        assert not result.valid
        assert any(e.code == "MISSING_RECORD_TYPE" for e in result.errors)

    def test_validate_missing_search_name(self):
        """Test validation fails when search name is missing."""
        step = SearchStep(
            record_type="gene",
            search_name="",
            parameters={},
        )
        strategy = StrategyAST(record_type="gene", root=step)

        result = validate_strategy(strategy)
        assert not result.valid
        assert any(e.code == "MISSING_SEARCH_NAME" for e in result.errors)

    def test_validate_combine_strategy(self):
        """Test validation of a combine strategy."""
        left = SearchStep(
            record_type="gene",
            search_name="GenesByGoTerm",
            parameters={"GoTerm": "GO:0016301"},
        )
        right = SearchStep(
            record_type="gene",
            search_name="GenesByExpression",
            parameters={"stage": "blood"},
        )
        combine = CombineStep(
            op=CombineOp.INTERSECT,
            left=left,
            right=right,
        )
        strategy = StrategyAST(record_type="gene", root=combine)

        result = validate_strategy(strategy)
        assert result.valid

    def test_validate_transform_strategy(self):
        """Test validation of a transform strategy."""
        search = SearchStep(
            record_type="gene",
            search_name="GenesByGoTerm",
            parameters={"GoTerm": "GO:0016301"},
        )
        transform = TransformStep(
            transform_name="GenesByOrthology",
            input=search,
            parameters={"taxon": "Toxoplasma"},
        )
        strategy = StrategyAST(record_type="gene", root=transform)

        result = validate_strategy(strategy)
        assert result.valid

    def test_validate_with_available_searches(self):
        """Test validation against available searches."""
        validator = StrategyValidator(
            available_searches={"gene": ["GenesByGoTerm", "GenesByExpression"]}
        )

        # Valid search
        step = SearchStep(
            record_type="gene",
            search_name="GenesByGoTerm",
            parameters={},
        )
        strategy = StrategyAST(record_type="gene", root=step)
        result = validator.validate(strategy)
        assert result.valid

        # Invalid search
        step = SearchStep(
            record_type="gene",
            search_name="NonexistentSearch",
            parameters={},
        )
        strategy = StrategyAST(record_type="gene", root=step)
        result = validator.validate(strategy)
        assert not result.valid
        assert any(e.code == "UNKNOWN_SEARCH" for e in result.errors)

