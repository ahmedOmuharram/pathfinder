"""Combine operations for strategy building.

Canonical set (matches WDK BooleanOperator): INTERSECT, MINUS, RMINUS, LONLY,
RONLY, COLOCATE, UNION. LONLY = left only (same as MINUS), RONLY = right only
(same as RMINUS); we keep both for round-trip fidelity with WDK.
"""

from enum import StrEnum
from typing import Literal, cast

from veupath_chatbot.platform.pydantic_base import CamelModel

# Order matches WDK; use this tuple for iteration / descriptions
COMBINE_OP_ORDER = (
    "INTERSECT",
    "MINUS",
    "RMINUS",
    "LONLY",
    "RONLY",
    "COLOCATE",
    "UNION",
)


class CombineOp(StrEnum):
    """Set operations for combining two step results."""

    INTERSECT = "INTERSECT"
    MINUS = "MINUS"
    RMINUS = "RMINUS"
    LONLY = "LONLY"
    RONLY = "RONLY"
    COLOCATE = "COLOCATE"
    UNION = "UNION"


DEFAULT_COMBINE_OPERATOR = CombineOp.INTERSECT

# For AI param descriptions
BOOLEAN_OPERATOR_OPTIONS_DESC = ", ".join(
    o.value for o in (CombineOp.INTERSECT, CombineOp.UNION, CombineOp.MINUS)
)

# User-friendly labels for operators
OP_LABELS: dict[CombineOp, str] = {
    CombineOp.INTERSECT: "IDs in common (AND)",
    CombineOp.UNION: "Combined (OR)",
    CombineOp.MINUS: "In left, not in right",
    CombineOp.RMINUS: "In right, not in left",
    CombineOp.LONLY: "Left only",
    CombineOp.RONLY: "Right only",
    CombineOp.COLOCATE: "Genomic colocation",
}


class ColocationParams(CamelModel):
    """Parameters for colocation operator."""

    upstream: int = 0
    downstream: int = 0
    strand: Literal["same", "opposite", "both"] = "both"

    @classmethod
    def from_raw(
        cls,
        operator: "CombineOp | None",
        upstream: int | None,
        downstream: int | None,
        strand: str | None,
    ) -> "ColocationParams | None":
        """Build ColocationParams if *operator* is COLOCATE, else None."""
        if operator != CombineOp.COLOCATE:
            return None
        strand_value: Literal["same", "opposite", "both"]
        if strand in ("same", "opposite", "both"):
            strand_value = cast("Literal['same', 'opposite', 'both']", strand)
        else:
            strand_value = "both"
        return cls(
            upstream=upstream or 0,
            downstream=downstream or 0,
            strand=strand_value,
        )

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


def get_wdk_operator(op: CombineOp) -> str:
    """Get WDK boolean operator name.

    Since enum values now match WDK values directly, this simply returns
    ``op.value`` (with a guard for COLOCATE which is not a boolean operator).

    :param op: Combine operator.
    :returns: WDK boolean operator name.
    :raises ValueError: If op is COLOCATE.
    """
    if op == CombineOp.COLOCATE:
        msg = "COLOCATE requires special handling, not boolean operator"
        raise ValueError(msg)
    return op.value


_OP_ALIASES: dict[str, CombineOp] = {
    "AND": CombineOp.INTERSECT,
    "INTERSECTION": CombineOp.INTERSECT,
    "OR": CombineOp.UNION,
    "PLUS": CombineOp.UNION,
    "UNION": CombineOp.UNION,
    "INTERSECT": CombineOp.INTERSECT,
    "MINUS": CombineOp.MINUS,
    "NOT": CombineOp.MINUS,
    "RMINUS": CombineOp.RMINUS,
    "LONLY": CombineOp.LONLY,
    "RONLY": CombineOp.RONLY,
    "LEFT_MINUS": CombineOp.MINUS,
    "RIGHT_MINUS": CombineOp.RMINUS,
    "LMINUS": CombineOp.MINUS,
    "MINUS_LEFT": CombineOp.MINUS,
    "MINUS_RIGHT": CombineOp.RMINUS,
    "COLOCATE": CombineOp.COLOCATE,
}


def parse_op(value: str) -> CombineOp:
    """Parse operator from string value.

    :param value: String value to parse.
    :returns: Parsed combine operator.
    :raises ValueError: If value is empty or unknown.
    """
    raw = (value or "").strip()
    if not raw:
        msg = "Unknown operator: <empty>"
        raise ValueError(msg)

    norm = raw.upper().replace("-", "_").replace(" ", "_")
    if norm in _OP_ALIASES:
        return _OP_ALIASES[norm]

    try:
        return CombineOp(norm)
    except ValueError as exc:
        msg = f"Unknown operator: {value}"
        raise ValueError(msg) from exc
