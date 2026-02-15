"""Combine operations for strategy building."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal


class CombineOp(StrEnum):
    """Set operations for combining two step results."""

    # IDs in common (AND) - intersection
    INTERSECT = "INTERSECT"

    # Combined (OR) - union
    UNION = "UNION"

    # Left minus right - IDs in left but not in right
    MINUS_LEFT = "MINUS_LEFT"

    # Right minus left - IDs in right but not in left
    MINUS_RIGHT = "MINUS_RIGHT"

    # Genomic colocation - genes near each other
    COLOCATE = "COLOCATE"


# User-friendly labels for operators
OP_LABELS: dict[CombineOp, str] = {
    CombineOp.INTERSECT: "IDs in common (AND)",
    CombineOp.UNION: "Combined (OR)",
    CombineOp.MINUS_LEFT: "In left, not in right",
    CombineOp.MINUS_RIGHT: "In right, not in left",
    CombineOp.COLOCATE: "Genomic colocation",
}

# Map to WDK boolean operator names
WDK_BOOLEAN_OPS: dict[CombineOp, str] = {
    CombineOp.INTERSECT: "INTERSECT",
    CombineOp.UNION: "UNION",
    CombineOp.MINUS_LEFT: "MINUS",  # Left minus (LMINUS rejected by WDK)
    CombineOp.MINUS_RIGHT: "RMINUS",  # Right minus
    # COLOCATE uses a different mechanism in WDK
}


@dataclass
class ColocationParams:
    """Parameters for colocation operator."""

    upstream: int = 0
    downstream: int = 0
    strand: Literal["same", "opposite", "both"] = "both"

    def validate(self) -> list[str]:
        """Validate parameters."""
        errors = []
        if self.upstream < 0:
            errors.append("Upstream distance must be non-negative")
        if self.downstream < 0:
            errors.append("Downstream distance must be non-negative")
        if self.strand not in ("same", "opposite", "both"):
            errors.append(f"Invalid strand option: {self.strand}")
        return errors


def get_op_label(op: CombineOp) -> str:
    """Get human-readable label for an operator.

    :param op: Combine operator.
    :returns: Human-readable label.
    """
    return OP_LABELS.get(op, op.value)


def get_wdk_operator(op: CombineOp) -> str:
    """Get WDK boolean operator name.

    :param op: Combine operator.
    :returns: WDK boolean operator name.
    :raises ValueError: If op is COLOCATE.
    """
    if op == CombineOp.COLOCATE:
        raise ValueError("COLOCATE requires special handling, not boolean operator")
    return WDK_BOOLEAN_OPS[op]


def parse_op(value: str) -> CombineOp:
    """Parse operator from string value.

    :param value: String value to parse.
    :returns: Parsed combine operator.
    :raises ValueError: If value is empty or unknown.
    """
    raw = (value or "").strip()
    if not raw:
        raise ValueError("Unknown operator: <empty>")

    # Normalize common user inputs.
    norm = raw.upper().replace("-", "_").replace(" ", "_")
    aliases: dict[str, CombineOp] = {
        "AND": CombineOp.INTERSECT,
        "INTERSECTION": CombineOp.INTERSECT,
        "OR": CombineOp.UNION,
        "PLUS": CombineOp.UNION,
        "UNION": CombineOp.UNION,
        "INTERSECT": CombineOp.INTERSECT,
        # Default MINUS to left-minus semantics (WDK boolean op name).
        "MINUS": CombineOp.MINUS_LEFT,
        "NOT": CombineOp.MINUS_LEFT,
        "MINUS_LEFT": CombineOp.MINUS_LEFT,
        "MINUS_RIGHT": CombineOp.MINUS_RIGHT,
        "LEFT_MINUS": CombineOp.MINUS_LEFT,
        "RIGHT_MINUS": CombineOp.MINUS_RIGHT,
        "LMINUS": CombineOp.MINUS_LEFT,
        "RMINUS": CombineOp.MINUS_RIGHT,
        # WDK BooleanOperator enum values for "only" variants
        # (semantically identical to minus: LONLY = left - right, RONLY = right - left)
        "LONLY": CombineOp.MINUS_LEFT,
        "RONLY": CombineOp.MINUS_RIGHT,
        "COLOCATE": CombineOp.COLOCATE,
    }
    if norm in aliases:
        return aliases[norm]

    # Fallback: accept exact enum values (case-insensitive).
    try:
        return CombineOp(norm)
    except ValueError as exc:
        raise ValueError(f"Unknown operator: {value}") from exc
