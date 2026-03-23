"""Tests for strategy DSL validation."""

import pytest
from pydantic import ValidationError

from veupath_chatbot.domain.strategy.ast import PlanStepNode, StrategyAST
from veupath_chatbot.domain.strategy.ops import ColocationParams, CombineOp
from veupath_chatbot.domain.strategy.validate import (
    StepValidationIssue,
    StrategyValidator,
    ValidationResult,
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

    def test_combine_missing_operator_rejected_at_construction(self) -> None:
        left = PlanStepNode(search_name="S1", parameters={})
        right = PlanStepNode(search_name="S2", parameters={})
        with pytest.raises(ValidationError):
            PlanStepNode(
                search_name="bool",
                primary_input=left,
                secondary_input=right,
                operator=None,
            )

    def test_colocate_missing_params_rejected_at_construction(self) -> None:
        left = PlanStepNode(search_name="S1", parameters={})
        right = PlanStepNode(search_name="S2", parameters={})
        with pytest.raises(ValidationError):
            PlanStepNode(
                search_name="bool",
                primary_input=left,
                secondary_input=right,
                operator=CombineOp.COLOCATE,
                colocation_params=None,
            )

    def test_validate_colocate_invalid_params(self) -> None:
        left = PlanStepNode(search_name="S1", parameters={})
        right = PlanStepNode(search_name="S2", parameters={})
        combine = PlanStepNode(
            search_name="bool",
            primary_input=left,
            secondary_input=right,
            operator=CombineOp.COLOCATE,
            colocation_params=ColocationParams(upstream=-1, downstream=0),
        )
        strategy = StrategyAST(record_type="gene", root=combine)
        result = validate_strategy(strategy)
        assert not result.valid
        assert any(e.code == "INVALID_COLOCATION_PARAMS" for e in result.errors)

    def test_validate_colocate_valid(self) -> None:
        left = PlanStepNode(search_name="S1", parameters={})
        right = PlanStepNode(search_name="S2", parameters={})
        combine = PlanStepNode(
            search_name="bool",
            primary_input=left,
            secondary_input=right,
            operator=CombineOp.COLOCATE,
            colocation_params=ColocationParams(
                upstream=100, downstream=200, strand="same"
            ),
        )
        strategy = StrategyAST(record_type="gene", root=combine)
        result = validate_strategy(strategy)
        assert result.valid

    def test_validate_empty_strategy(self) -> None:
        with pytest.raises(ValidationError):
            StrategyAST(record_type="gene", root=None)

    def test_recursive_validation_of_children(self) -> None:
        """Child nodes with missing searchName should be flagged."""
        left = PlanStepNode(search_name="", parameters={})
        right = PlanStepNode(search_name="S2", parameters={})
        combine = PlanStepNode(
            search_name="bool",
            primary_input=left,
            secondary_input=right,
            operator=CombineOp.INTERSECT,
        )
        strategy = StrategyAST(record_type="gene", root=combine)
        result = validate_strategy(strategy)
        assert not result.valid
        assert any(
            e.code == "MISSING_SEARCH_NAME" and "primaryInput" in e.path
            for e in result.errors
        )

    def test_recursive_validation_of_secondary_child(self) -> None:
        left = PlanStepNode(search_name="S1", parameters={})
        right = PlanStepNode(search_name="", parameters={})
        combine = PlanStepNode(
            search_name="bool",
            primary_input=left,
            secondary_input=right,
            operator=CombineOp.INTERSECT,
        )
        strategy = StrategyAST(record_type="gene", root=combine)
        result = validate_strategy(strategy)
        assert not result.valid
        assert any(
            e.code == "MISSING_SEARCH_NAME" and "secondaryInput" in e.path
            for e in result.errors
        )

    def test_unknown_search_in_child(self) -> None:
        """Available searches should be checked recursively in children."""
        validator = StrategyValidator(
            available_searches={"gene": ["S1"]},
        )
        left = PlanStepNode(search_name="S1", parameters={})
        right = PlanStepNode(search_name="UnknownSearch", parameters={})
        combine = PlanStepNode(
            search_name="bool",
            primary_input=left,
            secondary_input=right,
            operator=CombineOp.INTERSECT,
        )
        strategy = StrategyAST(record_type="gene", root=combine)
        result = validator.validate(strategy)
        assert not result.valid
        # "bool" root is also unknown, but secondaryInput child should be flagged
        assert any(
            e.code == "UNKNOWN_SEARCH" and "secondaryInput" in e.path
            for e in result.errors
        )

    def test_multiple_errors_accumulated(self) -> None:
        """Multiple errors should all appear."""
        leaf = PlanStepNode(search_name="", parameters={})
        strategy = StrategyAST(record_type="", root=leaf)
        result = validate_strategy(strategy)
        assert not result.valid
        codes = {e.code for e in result.errors}
        assert "MISSING_RECORD_TYPE" in codes
        assert "MISSING_SEARCH_NAME" in codes

    def test_colocate_both_negative_distances(self) -> None:
        left = PlanStepNode(search_name="S1", parameters={})
        right = PlanStepNode(search_name="S2", parameters={})
        combine = PlanStepNode(
            search_name="bool",
            primary_input=left,
            secondary_input=right,
            operator=CombineOp.COLOCATE,
            colocation_params=ColocationParams(upstream=-1, downstream=-2),
        )
        strategy = StrategyAST(record_type="gene", root=combine)
        result = validate_strategy(strategy)
        assert not result.valid
        colocation_errors = [
            e for e in result.errors if e.code == "INVALID_COLOCATION_PARAMS"
        ]
        assert len(colocation_errors) == 2


class TestValidationResult:
    def test_success(self) -> None:
        result = ValidationResult.success()
        assert result.valid is True
        assert result.errors == []

    def test_failure(self) -> None:
        err = StepValidationIssue(path="root", message="bad", code="BAD")
        result = ValidationResult.failure([err])
        assert result.valid is False
        assert len(result.errors) == 1
