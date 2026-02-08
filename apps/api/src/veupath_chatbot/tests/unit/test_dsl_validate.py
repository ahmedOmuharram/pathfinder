"""Tests for strategy DSL validation."""

from veupath_chatbot.domain.strategy.ast import PlanStepNode, StrategyAST
from veupath_chatbot.domain.strategy.ops import CombineOp
from veupath_chatbot.domain.strategy.validate import (
    StrategyValidator,
    validate_strategy,
)


class TestStrategyValidator:
    """Tests for StrategyValidator."""

    def test_validate_simple_search_strategy(self) -> None:
        """Test validation of a simple search strategy."""
        step = PlanStepNode(
            search_name="GenesByGoTerm", parameters={"GoTerm": "GO:0016301"}
        )
        strategy = StrategyAST(record_type="gene", root=step)

        result = validate_strategy(strategy)
        assert result.valid
        assert len(result.errors) == 0

    def test_validate_missing_record_type(self) -> None:
        """Test validation fails when record type is missing."""
        step = PlanStepNode(
            search_name="GenesByGoTerm", parameters={"GoTerm": "GO:0016301"}
        )
        strategy = StrategyAST(record_type="", root=step)

        result = validate_strategy(strategy)
        assert not result.valid
        assert any(e.code == "MISSING_RECORD_TYPE" for e in result.errors)

    def test_validate_missing_search_name(self) -> None:
        """Test validation fails when search name is missing."""
        step = PlanStepNode(search_name="", parameters={})
        strategy = StrategyAST(record_type="gene", root=step)

        result = validate_strategy(strategy)
        assert not result.valid
        assert any(e.code == "MISSING_SEARCH_NAME" for e in result.errors)

    def test_validate_combine_strategy(self) -> None:
        """Test validation of a combine strategy."""
        left = PlanStepNode(
            search_name="GenesByGoTerm", parameters={"GoTerm": "GO:0016301"}
        )
        right = PlanStepNode(
            search_name="GenesByExpression", parameters={"stage": "blood"}
        )
        combine = PlanStepNode(
            search_name="boolean_question_gene",
            operator=CombineOp.INTERSECT,
            primary_input=left,
            secondary_input=right,
        )
        strategy = StrategyAST(record_type="gene", root=combine)

        result = validate_strategy(strategy)
        assert result.valid

    def test_validate_transform_strategy(self) -> None:
        """Test validation of a transform strategy."""
        search = PlanStepNode(
            search_name="GenesByGoTerm", parameters={"GoTerm": "GO:0016301"}
        )
        transform = PlanStepNode(
            search_name="GenesByOrthology",
            primary_input=search,
            parameters={"taxon": "Toxoplasma"},
        )
        strategy = StrategyAST(record_type="gene", root=transform)

        result = validate_strategy(strategy)
        assert result.valid

    def test_validate_with_available_searches(self) -> None:
        """Test validation against available searches."""
        validator = StrategyValidator(
            available_searches={"gene": ["GenesByGoTerm", "GenesByExpression"]}
        )

        # Valid search
        step = PlanStepNode(search_name="GenesByGoTerm", parameters={})
        strategy = StrategyAST(record_type="gene", root=step)
        result = validator.validate(strategy)
        assert result.valid

        # Invalid search
        step = PlanStepNode(search_name="NonexistentSearch", parameters={})
        strategy = StrategyAST(record_type="gene", root=step)
        result = validator.validate(strategy)
        assert not result.valid
        assert any(e.code == "UNKNOWN_SEARCH" for e in result.errors)
