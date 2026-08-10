"""Validation for strategy DSL."""

from dataclasses import dataclass

from pydantic import JsonValue

from pathfinder.domain.parameters.values import to_decoded_map
from pathfinder.domain.strategy.ast import StrategyStepNode
from pathfinder.domain.strategy.ops import CombineOp
from pathfinder.domain.strategy.organism import extract_output_organisms


@dataclass
class StepValidationIssue:
    """A single validation issue found during step/strategy validation."""

    path: str
    message: str
    code: str


@dataclass
class ValidationResult:
    """Result of validation."""

    valid: bool
    errors: list[StepValidationIssue]

    @classmethod
    def success(cls) -> ValidationResult:
        """Create a successful result."""
        return cls(valid=True, errors=[])

    @classmethod
    def failure(cls, errors: list[StepValidationIssue]) -> ValidationResult:
        """Create a failed result.

        :param errors: Validation errors list.

        """
        return cls(valid=False, errors=errors)


class StrategyValidator:
    """Validates strategy AST."""

    def __init__(
        self,
        available_searches: dict[str, list[str]] | None = None,
        available_transforms: list[str] | None = None,
    ) -> None:
        """Initialize validator.

        :param available_searches: Map of record_type -> list of search names.
        :param available_transforms: List of available transform names.
        """
        self.available_searches = available_searches or {}
        self.available_transforms = available_transforms or []

    def validate(self, root: StrategyStepNode, record_type: str) -> ValidationResult:
        """Validate a strategy tree.

        :param root: Root node of the strategy tree.
        :param record_type: Record type (e.g. "gene", "transcript").

        """
        errors: list[StepValidationIssue] = []

        # Validate record type
        if not record_type:
            errors.append(
                StepValidationIssue(
                    path="recordType",
                    message="Record type is required",
                    code="MISSING_RECORD_TYPE",
                )
            )

        # Validate the tree
        self._validate_node(root, "root", record_type, errors)

        return (
            ValidationResult.success()
            if not errors
            else ValidationResult.failure(errors)
        )

    def _validate_contrast_samples(
        self,
        node: StrategyStepNode,
        path: str,
        errors: list[StepValidationIssue],
    ) -> None:
        """Reject a differential search contrasting a group against itself.

        Any ``*_ref_*`` / ``*_comp_*`` pair (fold change ``samples_fc_*``,
        DESeq ``samples_de_*``, and the percentile variant) names the two
        sides of a contrast. Setting both to the same group pushes and runs;
        it just cannot mean anything, which is why it needs catching here
        rather than in the results.
        """
        decoded = to_decoded_map(node.parameters)
        pairs: list[tuple[str, JsonValue, JsonValue]] = []
        for ref_name, ref_value in decoded.items():
            if "_ref_" not in ref_name:
                continue
            comp_value = decoded.get(ref_name.replace("_ref_", "_comp_"))
            if comp_value is not None:
                pairs.append((ref_name, ref_value, comp_value))
        percentile = decoded.get("samples_percentile_generic")
        comp = decoded.get("samples_fc_comp_generic")
        if percentile is not None and comp is not None:
            pairs.append(("samples_percentile_generic", percentile, comp))

        for param_name, ref_value, comp_value in pairs:
            if ref_value and comp_value and str(ref_value) == str(comp_value):
                errors.append(
                    StepValidationIssue(
                        path=f"{path}.parameters.{param_name}",
                        message=(
                            "Reference and comparison samples are identical "
                            f"({ref_value}) - this contrasts a group against "
                            "itself and produces meaningless differential "
                            "results. Set different samples for reference vs "
                            "comparison."
                        ),
                        code="IDENTICAL_CONTRAST_SAMPLES",
                    )
                )

    def _validate_cross_organism_intersect(
        self,
        node: StrategyStepNode,
        path: str,
        errors: list[StepValidationIssue],
    ) -> None:
        """Reject INTERSECT between disjoint organism scopes.

        Gene IDs from different species never match, so the result is always
        zero. Only fires when both sides have a known scope; an unknown scope
        must not block a legitimate strategy. UNION is left alone - combining
        species is meaningful.
        """
        if node.operator is not CombineOp.INTERSECT:
            return
        if node.primary_input is None or node.secondary_input is None:
            return
        primary = extract_output_organisms(node.primary_input)
        secondary = extract_output_organisms(node.secondary_input)
        if primary is None or secondary is None or not primary.isdisjoint(secondary):
            return
        errors.append(
            StepValidationIssue(
                path=f"{path}.operator",
                message=(
                    "Cannot INTERSECT steps with different organism scopes "
                    f"({', '.join(sorted(primary))} vs "
                    f"{', '.join(sorted(secondary))}). Gene IDs from different "
                    "species never match, so this always returns 0 results. "
                    "Apply organism-specific filters BEFORE any ortholog "
                    "transform, not after."
                ),
                code="CROSS_ORGANISM_INTERSECT",
            )
        )

    def _validate_combine_node(
        self,
        node: StrategyStepNode,
        path: str,
        errors: list[StepValidationIssue],
    ) -> None:
        """Validate combine-specific constraints on a node."""
        if node.operator is None:
            errors.append(
                StepValidationIssue(
                    path=f"{path}.operator",
                    message="operator is required for combine nodes",
                    code="MISSING_OPERATOR",
                )
            )
        elif node.operator not in CombineOp:
            errors.append(
                StepValidationIssue(
                    path=f"{path}.operator",
                    message=f"Invalid operator: {node.operator}",
                    code="INVALID_OPERATOR",
                )
            )
        if node.primary_input is None or node.secondary_input is None:
            errors.append(
                StepValidationIssue(
                    path=path,
                    message="Combine nodes require two inputs",
                    code="MISSING_INPUT",
                )
            )
        if node.operator == CombineOp.COLOCATE and node.colocation_params is None:
            errors.append(
                StepValidationIssue(
                    path=f"{path}.colocationParams",
                    message="colocationParams is required for COLOCATE",
                    code="MISSING_COLOCATION_PARAMS",
                )
            )

    def _validate_node(
        self,
        node: StrategyStepNode,
        path: str,
        expected_record_type: str,
        errors: list[StepValidationIssue],
    ) -> None:
        """Validate a single node in the AST.

        :param node: Plan step node.
        :param path: Node path.
        :param expected_record_type: Expected record type.
        :param errors: Validation errors list.

        """
        if not node.search_name:
            errors.append(
                StepValidationIssue(
                    path=f"{path}.searchName",
                    message="searchName is required",
                    code="MISSING_SEARCH_NAME",
                )
            )

        if self.available_searches:
            rt_searches = self.available_searches.get(expected_record_type, [])
            if node.search_name and node.search_name not in rt_searches:
                errors.append(
                    StepValidationIssue(
                        path=f"{path}.searchName",
                        message=f"Unknown search: {node.search_name}",
                        code="UNKNOWN_SEARCH",
                    )
                )

        self._validate_contrast_samples(node, path, errors)

        if node.infer_kind() == "combine":
            self._validate_combine_node(node, path, errors)
            self._validate_cross_organism_intersect(node, path, errors)

        if node.secondary_input is not None:
            self._validate_node(
                node.secondary_input,
                f"{path}.secondaryInput",
                expected_record_type,
                errors,
            )
        if node.primary_input is not None:
            self._validate_node(
                node.primary_input, f"{path}.primaryInput", expected_record_type, errors
            )


def validate_strategy(root: StrategyStepNode, record_type: str) -> ValidationResult:
    """Validate a strategy tree with default validator.

    :param root: Root node of the strategy tree.
    :param record_type: Record type (e.g. "gene", "transcript").

    """
    return StrategyValidator().validate(root, record_type)
