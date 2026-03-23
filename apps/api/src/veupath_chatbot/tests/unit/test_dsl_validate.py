"""Tests for strategy DSL validation."""

from veupath_chatbot.domain.strategy.ast import PlanStepNode
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

        result = validate_strategy(step, "gene")
        assert result.valid
        assert len(result.errors) == 0

    def test_validate_missing_record_type(self) -> None:
        """Test validation fails when record type is missing."""
        step = PlanStepNode(
            search_name="GenesByGoTerm", parameters={"GoTerm": "GO:0016301"}
        )

        result = validate_strategy(step, "")
        assert not result.valid
        assert any(e.code == "MISSING_RECORD_TYPE" for e in result.errors)

    def test_validate_missing_search_name(self) -> None:
        """Test validation fails when search name is missing."""
        step = PlanStepNode(search_name="", parameters={})

        result = validate_strategy(step, "gene")
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

        result = validate_strategy(combine, "gene")
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

        result = validate_strategy(transform, "gene")
        assert result.valid

    def test_validate_with_available_searches(self) -> None:
        """Test validation against available searches."""
        validator = StrategyValidator(
            available_searches={"gene": ["GenesByGoTerm", "GenesByExpression"]}
        )

        # Valid search
        step = PlanStepNode(search_name="GenesByGoTerm", parameters={})
        result = validator.validate(step, "gene")
        assert result.valid

        # Invalid search
        step = PlanStepNode(search_name="NonexistentSearch", parameters={})
        result = validator.validate(step, "gene")
        assert not result.valid
        assert any(e.code == "UNKNOWN_SEARCH" for e in result.errors)

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
        result = validate_strategy(combine, "gene")
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
        result = validate_strategy(combine, "gene")
        assert result.valid

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
        result = validate_strategy(combine, "gene")
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
        result = validate_strategy(combine, "gene")
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
        result = validator.validate(combine, "gene")
        assert not result.valid
        # "bool" root is also unknown, but secondaryInput child should be flagged
        assert any(
            e.code == "UNKNOWN_SEARCH" and "secondaryInput" in e.path
            for e in result.errors
        )

    def test_multiple_errors_accumulated(self) -> None:
        """Multiple errors should all appear."""
        leaf = PlanStepNode(search_name="", parameters={})
        result = validate_strategy(leaf, "")
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
        result = validate_strategy(combine, "gene")
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
