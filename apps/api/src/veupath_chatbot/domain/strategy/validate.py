"""Validation for strategy DSL."""

from dataclasses import dataclass

from veupath_chatbot.domain.strategy.ast import (
    PlanStepNode,
    StrategyAST,
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
        node: PlanStepNode,
        path: str,
        expected_record_type: str,
        errors: list[ValidationError],
    ) -> None:
        """Validate a single node in the AST."""
        kind = node.infer_kind()

        if not node.search_name:
            errors.append(
                ValidationError(
                    path=f"{path}.searchName",
                    message="searchName is required",
                    code="MISSING_SEARCH_NAME",
                )
            )

        if self.available_searches:
            rt_searches = self.available_searches.get(expected_record_type, [])
            if node.search_name and node.search_name not in rt_searches:
                errors.append(
                    ValidationError(
                        path=f"{path}.searchName",
                        message=f"Unknown search: {node.search_name}",
                        code="UNKNOWN_SEARCH",
                    )
                )

        if kind == "combine":
            if node.operator is None:
                errors.append(
                    ValidationError(
                        path=f"{path}.operator",
                        message="operator is required for combine nodes",
                        code="MISSING_OPERATOR",
                    )
                )
            elif node.operator not in CombineOp:
                errors.append(
                    ValidationError(
                        path=f"{path}.operator",
                        message=f"Invalid operator: {node.operator}",
                        code="INVALID_OPERATOR",
                    )
                )
            if node.primary_input is None or node.secondary_input is None:
                errors.append(
                    ValidationError(
                        path=path,
                        message="Combine nodes require two inputs",
                        code="MISSING_INPUT",
                    )
                )
            if node.operator == CombineOp.COLOCATE:
                if node.colocation_params is None:
                    errors.append(
                        ValidationError(
                            path=f"{path}.colocationParams",
                            message="colocationParams is required for COLOCATE",
                            code="MISSING_COLOCATION_PARAMS",
                        )
                    )
                else:
                    for err in node.colocation_params.validate():
                        errors.append(
                            ValidationError(
                                path=f"{path}.colocationParams",
                                message=err,
                                code="INVALID_COLOCATION_PARAMS",
                            )
                        )

        if node.secondary_input is not None:
            self._validate_node(
                node.secondary_input, f"{path}.secondaryInput", expected_record_type, errors
            )
        if node.primary_input is not None:
            self._validate_node(
                node.primary_input, f"{path}.primaryInput", expected_record_type, errors
            )


def validate_strategy(strategy: StrategyAST) -> ValidationResult:
    """Validate a strategy AST with default validator."""
    return StrategyValidator().validate(strategy)

