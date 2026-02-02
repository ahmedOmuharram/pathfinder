"""Validation for strategy DSL."""

from dataclasses import dataclass

from veupath_chatbot.domain.strategy.ast import (
    CombineStep,
    SearchStep,
    StepNode,
    StrategyAST,
    TransformStep,
)
from veupath_chatbot.domain.strategy.ops import CombineOp


@dataclass
class ValidationError:
    """A validation error."""

    path: str
    message: str
    code: str


@dataclass
class ValidationResult:
    """Result of validation."""

    valid: bool
    errors: list[ValidationError]

    @classmethod
    def success(cls) -> "ValidationResult":
        """Create a successful result."""
        return cls(valid=True, errors=[])

    @classmethod
    def failure(cls, errors: list[ValidationError]) -> "ValidationResult":
        """Create a failed result."""
        return cls(valid=False, errors=errors)


class StrategyValidator:
    """Validates strategy AST."""

    def __init__(
        self,
        available_searches: dict[str, list[str]] | None = None,
        available_transforms: list[str] | None = None,
    ) -> None:
        """Initialize validator.

        Args:
            available_searches: Map of record_type -> list of search names
            available_transforms: List of available transform names
        """
        self.available_searches = available_searches or {}
        self.available_transforms = available_transforms or []

    def validate(self, strategy: StrategyAST) -> ValidationResult:
        """Validate a strategy AST."""
        errors: list[ValidationError] = []

        # Validate record type
        if not strategy.record_type:
            errors.append(
                ValidationError(
                    path="recordType",
                    message="Record type is required",
                    code="MISSING_RECORD_TYPE",
                )
            )

        # Validate the tree
        self._validate_node(strategy.root, "root", strategy.record_type, errors)

        # Check for empty strategy
        if strategy.root is None:
            errors.append(
                ValidationError(
                    path="root",
                    message="Strategy must have at least one step",
                    code="EMPTY_STRATEGY",
                )
            )

        return ValidationResult.success() if not errors else ValidationResult.failure(errors)

    def _validate_node(
        self,
        node: StepNode,
        path: str,
        expected_record_type: str,
        errors: list[ValidationError],
    ) -> None:
        """Validate a single node in the AST."""
        if isinstance(node, SearchStep):
            self._validate_search_step(node, path, expected_record_type, errors)
        elif isinstance(node, CombineStep):
            self._validate_combine_step(node, path, expected_record_type, errors)
        elif isinstance(node, TransformStep):
            self._validate_transform_step(node, path, expected_record_type, errors)

    def _validate_search_step(
        self,
        step: SearchStep,
        path: str,
        expected_record_type: str,
        errors: list[ValidationError],
    ) -> None:
        """Validate a search step."""
        if not step.search_name:
            errors.append(
                ValidationError(
                    path=f"{path}.searchName",
                    message="Search name is required",
                    code="MISSING_SEARCH_NAME",
                )
            )

        if self.available_searches:
            rt_searches = self.available_searches.get(expected_record_type, [])
            if step.search_name and step.search_name not in rt_searches:
                errors.append(
                    ValidationError(
                        path=f"{path}.searchName",
                        message=f"Unknown search: {step.search_name}",
                        code="UNKNOWN_SEARCH",
                    )
                )

    def _validate_combine_step(
        self,
        step: CombineStep,
        path: str,
        expected_record_type: str,
        errors: list[ValidationError],
    ) -> None:
        """Validate a combine step."""
        if step.op not in CombineOp:
            errors.append(
                ValidationError(
                    path=f"{path}.operator",
                    message=f"Invalid operator: {step.op}",
                    code="INVALID_OPERATOR",
                )
            )

        if step.op == CombineOp.COLOCATE and step.colocation_params:
            for err in step.colocation_params.validate():
                errors.append(
                    ValidationError(
                        path=f"{path}.colocationParams",
                        message=err,
                        code="INVALID_COLOCATION_PARAMS",
                    )
                )

        self._validate_node(step.left, f"{path}.left", expected_record_type, errors)
        self._validate_node(step.right, f"{path}.right", expected_record_type, errors)

    def _validate_transform_step(
        self,
        step: TransformStep,
        path: str,
        expected_record_type: str,
        errors: list[ValidationError],
    ) -> None:
        """Validate a transform step."""
        if not step.transform_name:
            errors.append(
                ValidationError(
                    path=f"{path}.transformName",
                    message="Transform name is required",
                    code="MISSING_TRANSFORM_NAME",
                )
            )

        if self.available_transforms and step.transform_name not in self.available_transforms:
            errors.append(
                ValidationError(
                    path=f"{path}.transformName",
                    message=f"Unknown transform: {step.transform_name}",
                    code="UNKNOWN_TRANSFORM",
                )
            )

        self._validate_node(step.input, f"{path}.input", expected_record_type, errors)


def validate_strategy(strategy: StrategyAST) -> ValidationResult:
    """Validate a strategy AST with default validator."""
    return StrategyValidator().validate(strategy)

