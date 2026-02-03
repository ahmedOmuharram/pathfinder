"""Generate human-readable explanations of strategies."""

from veupath_chatbot.domain.strategy.ast import (
    PlanStepNode,
    StrategyAST,
)
from veupath_chatbot.domain.strategy.ops import CombineOp, get_op_label


def explain_strategy(strategy: StrategyAST) -> str:
    """Generate a human-readable explanation of a strategy."""
    lines = [
        f"**Strategy: {strategy.name or 'Untitled'}**",
        f"Record type: {strategy.record_type}",
        "",
        "**Steps:**",
    ]

    step_num = 0

    def explain_node(node: PlanStepNode, indent: int = 0) -> list[str]:
        nonlocal step_num
        step_num += 1
        prefix = "  " * indent

        kind = node.infer_kind()

        if kind == "search":
            return [
                f"{prefix}{step_num}. **Search**: {node.display_name or node.search_name}",
                f"{prefix}   Parameters: {_format_params(node.parameters)}",
            ]

        if kind == "combine":
            left_lines = explain_node(node.primary_input, indent + 1) if node.primary_input else []
            right_lines = explain_node(node.secondary_input, indent + 1) if node.secondary_input else []

            op_label = get_op_label(node.operator) if node.operator else "Unknown"
            result = [
                f"{prefix}{step_num}. **Combine** ({op_label}):",
                f"{prefix}   Left input:",
            ]
            result.extend(left_lines)
            result.append(f"{prefix}   Right input:")
            result.extend(right_lines)

            if node.operator == CombineOp.COLOCATE and node.colocation_params:
                cp = node.colocation_params
                result.append(
                    f"{prefix}   Colocation: ±{cp.upstream}bp upstream, "
                    f"±{cp.downstream}bp downstream, {cp.strand} strand"
                )

            return result

        if kind == "transform":
            input_lines = (
                explain_node(node.primary_input, indent + 1) if node.primary_input else []
            )

            result = [
                f"{prefix}{step_num}. **Transform**: {node.display_name or node.search_name}",
            ]
            if node.parameters:
                result.append(f"{prefix}   Parameters: {_format_params(node.parameters)}")
            result.append(f"{prefix}   Input:")
            result.extend(input_lines)

            return result

        return []

    lines.extend(explain_node(strategy.root))

    if strategy.description:
        lines.extend(["", f"**Description:** {strategy.description}"])

    return "\n".join(lines)


def explain_step(step: PlanStepNode) -> str:
    """Generate a short explanation of a single step."""
    kind = step.infer_kind()
    if kind == "search":
        return f"Search: {step.display_name or step.search_name}"
    if kind == "combine":
        op_label = get_op_label(step.operator) if step.operator else "Unknown"
        return f"Combine ({op_label})"
    if kind == "transform":
        return f"Transform: {step.display_name or step.search_name}"
    return "Unknown step"


def explain_operation(op: CombineOp) -> str:
    """Explain what a combine operation does."""
    explanations = {
        CombineOp.INTERSECT: (
            "Returns records that appear in **both** input sets. "
            "Use this to find records that match multiple criteria."
        ),
        CombineOp.UNION: (
            "Returns records that appear in **either** input set. "
            "Use this to combine results from different searches."
        ),
        CombineOp.MINUS_LEFT: (
            "Returns records from the **left** set that are **not** in the right set. "
            "Use this to exclude certain records from your results."
        ),
        CombineOp.MINUS_RIGHT: (
            "Returns records from the **right** set that are **not** in the left set. "
            "The opposite of left minus."
        ),
        CombineOp.COLOCATE: (
            "Returns records from the left set that are **genomically near** "
            "records in the right set. Use this to find genes near other features."
        ),
    }
    return explanations.get(op, f"Combine operation: {op.value}")


def _format_params(params: dict) -> str:
    """Format parameters for display."""
    if not params:
        return "(none)"

    items = []
    for key, value in params.items():
        if isinstance(value, list):
            value = ", ".join(str(v) for v in value)
        items.append(f"{key}={value}")

    return ", ".join(items)

