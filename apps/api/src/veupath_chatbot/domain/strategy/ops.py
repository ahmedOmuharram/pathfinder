"""Combine operations for strategy building.

Canonical set (matches WDK BooleanOperator): INTERSECT, MINUS, RMINUS, LONLY,
RONLY, COLOCATE, UNION. LONLY = left only (same as MINUS), RONLY = right only
(same as RMINUS); we keep both for round-trip fidelity with WDK.
"""

from enum import StrEnum
from typing import Literal

from pydantic import Field

from veupath_chatbot.platform.pydantic_base import CamelModel


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


class ColocationParams(CamelModel):
    """Full WDK GenesBySpanLogic parameters for COLOCATE operator.

    Human-readable field values for the AI model; ``to_wdk_params()``
    translates to WDK internal vocabulary values before submission.

    WDK source of truth:
    ``GET /record-types/transcript/searches/GenesBySpanLogic?expandParams=true``
    """

    # High-level
    operation: Literal["overlaps", "contains", "is contained in"] = "overlaps"
    strand: Literal["either strand", "same strand", "opposite strand"] = (
        "either strand"
    )
    output: Literal["a", "b"] = "a"

    # Region A (gene result set) — default: 1kb upstream of gene start
    region_a: Literal["exact", "upstream", "downstream", "custom"] = "custom"
    begin_a: Literal["start", "stop"] = "start"
    begin_direction_a: Literal["+", "-"] = "-"
    begin_offset_a: int = Field(default=1000, ge=0)
    end_a: Literal["start", "stop"] = "stop"
    end_direction_a: Literal["+", "-"] = "+"
    end_offset_a: int = Field(default=0, ge=0)

    # Region B (feature set)
    region_b: Literal["exact", "upstream", "downstream", "custom"] = "exact"
    begin_b: Literal["start", "stop"] = "start"
    begin_direction_b: Literal["+", "-"] = "+"
    begin_offset_b: int = Field(default=0, ge=0)
    end_b: Literal["start", "stop"] = "stop"
    end_direction_b: Literal["+", "-"] = "+"
    end_offset_b: int = Field(default=0, ge=0)

    def to_wdk_params(self) -> dict[str, str]:
        """Serialize to the WDK GenesBySpanLogic parameter dict.

        Translates human-readable Literal values to WDK internal
        vocabulary values (first column of each param's vocabulary array).
        """
        return {
            "span_sentence": "colocation",
            "span_operation": _OPERATION_TO_WDK[self.operation],
            "span_strand": _STRAND_TO_WDK[self.strand],
            "span_output": self.output,
            "region_a": self.region_a,
            "span_begin_a": self.begin_a,
            "span_begin_direction_a": self.begin_direction_a,
            "span_begin_offset_a": str(self.begin_offset_a),
            "span_end_a": self.end_a,
            "span_end_direction_a": self.end_direction_a,
            "span_end_offset_a": str(self.end_offset_a),
            "region_b": self.region_b,
            "span_begin_b": self.begin_b,
            "span_begin_direction_b": self.begin_direction_b,
            "span_begin_offset_b": str(self.begin_offset_b),
            "span_end_b": self.end_b,
            "span_end_direction_b": self.end_direction_b,
            "span_end_offset_b": str(self.end_offset_b),
        }


# WDK vocabulary: [internal_value, display_value].
# ColocationParams uses display (human-readable) values; these maps
# translate to the WDK internal values expected by the REST API.
_OPERATION_TO_WDK: dict[str, str] = {
    "overlaps": "overlap",
    "contains": "a_contain_b",
    "is contained in": "b_contain_a",
}

_STRAND_TO_WDK: dict[str, str] = {
    "either strand": "Both strands",
    "same strand": "same strand",
    "opposite strand": "opposite strand",
}


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
