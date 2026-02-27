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
    MINUS = "MINUS"

    # Right minus left - IDs in right but not in left
    RMINUS = "RMINUS"

    # Genomic colocation - genes near each other
    COLOCATE = "COLOCATE"


# User-friendly labels for operators
OP_LABELS: dict[CombineOp, str] = {
    CombineOp.INTERSECT: "IDs in common (AND)",
    CombineOp.UNION: "Combined (OR)",
    CombineOp.MINUS: "In left, not in right",
    CombineOp.RMINUS: "In right, not in left",
    CombineOp.COLOCATE: "Genomic colocation",
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

    Since enum values now match WDK values directly, this simply returns
    ``op.value`` (with a guard for COLOCATE which is not a boolean operator).

    :param op: Combine operator.
    :returns: WDK boolean operator name.
    :raises ValueError: If op is COLOCATE.
    """
    if op == CombineOp.COLOCATE:
        raise ValueError("COLOCATE requires special handling, not boolean operator")
    return op.value


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
        "MINUS": CombineOp.MINUS,
        "NOT": CombineOp.MINUS,
        "RMINUS": CombineOp.RMINUS,
        "LEFT_MINUS": CombineOp.MINUS,
        "RIGHT_MINUS": CombineOp.RMINUS,
        "LMINUS": CombineOp.MINUS,
        "LONLY": CombineOp.MINUS,
        "RONLY": CombineOp.RMINUS,
        # Back-compat: old internal names
        "MINUS_LEFT": CombineOp.MINUS,
        "MINUS_RIGHT": CombineOp.RMINUS,
        "COLOCATE": CombineOp.COLOCATE,
    }
    if norm in aliases:
        return aliases[norm]

    # Fallback: accept exact enum values (case-insensitive).
    try:
        return CombineOp(norm)
    except ValueError as exc:
        raise ValueError(f"Unknown operator: {value}") from exc
