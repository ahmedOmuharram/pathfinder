from __future__ import annotations

import re
from collections.abc import Collection, Mapping
from enum import StrEnum
from typing import Literal

from assistant_core.platform.pydantic_base import CamelModel
from pydantic import Field


class ConstraintKind(StrEnum):
    DATA_TYPE = "data_type"
    STATISTICAL_THRESHOLD = "statistical_threshold"
    FOLD_CHANGE = "fold_change"
    COMPARATOR = "comparator"
    ORGANISM = "organism"
    RECORD_TYPE = "record_type"
    PERCENTILE = "percentile"
    OTHER = "other"


class ConstraintSource(StrEnum):
    USER_EXPLICIT = "user_explicit"
    ASSUMED = "assumed"


class ConstraintStatus(StrEnum):
    PROVISIONAL = "provisional"
    GROUNDED = "grounded"
    SUBSTITUTED = "substituted"
    UNGROUNDABLE = "ungroundable"


class Constraint(CamelModel):
    kind: ConstraintKind
    requested_value: str = Field(min_length=1)
    label: str = Field(min_length=1)
    source: ConstraintSource = ConstraintSource.ASSUMED
    hard: bool = True
    """A hard requirement ('RNA-Seq only') blocks if unmet; a soft preference
    ('RNA-Seq preferred, microarray fallback ok') is surfaced but never blocks."""


class GroundedConstraint(CamelModel):
    constraint: Constraint
    status: ConstraintStatus
    realized_value: str | None = None
    note: str = ""


_UNMET = {ConstraintStatus.UNGROUNDABLE, ConstraintStatus.SUBSTITUTED}


def is_blocking(grounded: GroundedConstraint) -> bool:
    return (
        grounded.constraint.source is ConstraintSource.USER_EXPLICIT
        and grounded.constraint.hard
        and grounded.status in _UNMET
    )


def provisional_constraints(constraints: list[Constraint]) -> list[GroundedConstraint]:
    """Wrap constraints as ``provisional`` — captured but not yet grounded (no
    plan exists to compare against). Provisional constraints never block; they
    surface in the ledger so the user sees what was captured pre-plan."""

    return [
        GroundedConstraint(constraint=c, status=ConstraintStatus.PROVISIONAL)
        for c in constraints
    ]


def merge_constraints(
    provisional: list[Constraint], explicit: list[Constraint]
) -> list[Constraint]:
    """Merge scoping's provisional (assumed) constraints with constraints the
    user stated in their latest message. The explicit set wins per dimension
    (``kind``) and is forced to ``user_explicit`` — anything the user literally
    states is explicit by construction, regardless of how the LLM tagged it."""

    by_kind: dict[ConstraintKind, Constraint] = {c.kind: c for c in provisional}
    for c in explicit:
        by_kind[c.kind] = c.model_copy(
            update={"source": ConstraintSource.USER_EXPLICIT}
        )
    return list(by_kind.values())


_SIGNIFICANCE_RE = re.compile(
    r"p_?value|p_?adj|fdr|q_?value|significance", re.IGNORECASE
)
_MICROARRAY_RE = re.compile(r"microarray", re.IGNORECASE)
_RNASEQ_REQUEST_RE = re.compile(r"rna[\s_-]?seq", re.IGNORECASE)
_EXPRESSION_SEARCH_RE = re.compile(r"rnaseq|microarray", re.IGNORECASE)


class _RealizedSpec(CamelModel):
    """The bound facts a constraint is grounded against: the criteria's WDK
    search names, the union of their parameter names, and the values bound to
    them."""

    search_names: list[str] = Field(default_factory=list)
    param_names: frozenset[str] = Field(default_factory=frozenset)
    param_values: dict[str, str] = Field(default_factory=dict)


def _ground_data_type(c: Constraint, realized: _RealizedSpec) -> GroundedConstraint:
    expr = [s for s in realized.search_names if _EXPRESSION_SEARCH_RE.search(s)]
    if not expr:
        return GroundedConstraint(
            constraint=c,
            status=ConstraintStatus.UNGROUNDABLE,
            note="no expression search in the strategy",
        )
    wants_rnaseq = bool(_RNASEQ_REQUEST_RE.search(c.requested_value))
    all_microarray = all(_MICROARRAY_RE.search(s) for s in expr)
    if wants_rnaseq and all_microarray:
        return GroundedConstraint(
            constraint=c,
            status=ConstraintStatus.SUBSTITUTED,
            realized_value="microarray",
            note="requested RNA-Seq but only microarray searches were selected",
        )
    return GroundedConstraint(
        constraint=c,
        status=ConstraintStatus.GROUNDED,
        realized_value="rna-seq" if wants_rnaseq else "microarray",
    )


def _ground_threshold(c: Constraint, realized: _RealizedSpec) -> GroundedConstraint:
    if any(_SIGNIFICANCE_RE.search(name) for name in realized.param_names):
        return GroundedConstraint(constraint=c, status=ConstraintStatus.GROUNDED)
    return GroundedConstraint(
        constraint=c,
        status=ConstraintStatus.UNGROUNDABLE,
        note="no selected search exposes a significance parameter",
    )


def _ground_fold_change(c: Constraint, realized: _RealizedSpec) -> GroundedConstraint:
    if any("fold_change" in name for name in realized.param_names):
        return GroundedConstraint(constraint=c, status=ConstraintStatus.GROUNDED)
    return GroundedConstraint(
        constraint=c,
        status=ConstraintStatus.UNGROUNDABLE,
        note="no fold_change parameter in the strategy",
    )


_PERCENTILE_PARAM_RE = re.compile(r"percentile", re.IGNORECASE)
_SHARE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:%|percent\b)", re.IGNORECASE)
_TOP_RE = re.compile(r"\btop\b|\bhighest\b", re.IGNORECASE)
_BOTTOM_RE = re.compile(r"\bbottom\b|\blowest\b", re.IGNORECASE)
_FULL_SCALE = 100.0
# A "top" share is a lower bound on the percentile; a "bottom" share is an
# upper bound. The name of the WDK parameter says which end it holds.
_BOUND_WORD: dict[str, str] = {"top": "min", "bottom": "max"}


def _plain(number: float) -> str:
    return str(int(number)) if number.is_integer() else str(number)


class PercentileRequest(CamelModel):
    """A share of a ranked population, read from what the user stated."""

    direction: Literal["top", "bottom"]
    share: float

    @classmethod
    def parse(cls, text: str) -> PercentileRequest | None:
        share = _SHARE_RE.search(text)
        if share is None:
            return None
        if _TOP_RE.search(text):
            direction: Literal["top", "bottom"] = "top"
        elif _BOTTOM_RE.search(text):
            direction = "bottom"
        else:
            return None
        return cls(direction=direction, share=float(share.group(1)))

    @property
    def bound(self) -> float:
        """The percentile value that realizes this share."""
        return _FULL_SCALE - self.share if self.direction == "top" else self.share

    def share_of(self, bound: float) -> float:
        return _FULL_SCALE - bound if self.direction == "top" else bound


def _percentile_bound(
    request: PercentileRequest, realized: _RealizedSpec
) -> tuple[str, str] | None:
    named = {
        name: value
        for name, value in realized.param_values.items()
        if _PERCENTILE_PARAM_RE.search(name)
    }
    if not named:
        return None
    word = _BOUND_WORD[request.direction]
    at_end = {name: value for name, value in named.items() if word in name.lower()}
    chosen = at_end or named
    if len(chosen) != 1:
        return None
    return next(iter(chosen.items()))


def _ground_percentile(c: Constraint, realized: _RealizedSpec) -> GroundedConstraint:
    request = PercentileRequest.parse(f"{c.requested_value} {c.label}")
    if request is None:
        return GroundedConstraint(
            constraint=c,
            status=ConstraintStatus.UNGROUNDABLE,
            note="the requested share and direction could not be read",
        )
    found = _percentile_bound(request, realized)
    if found is None:
        return GroundedConstraint(
            constraint=c,
            status=ConstraintStatus.UNGROUNDABLE,
            note="no percentile parameter in the strategy",
        )
    name, raw = found
    try:
        bound = float(raw)
    except ValueError:
        return GroundedConstraint(
            constraint=c,
            status=ConstraintStatus.UNGROUNDABLE,
            realized_value=raw,
            note=f"{name} holds {raw!r}, which is not a percentile",
        )
    if bound == request.bound:
        return GroundedConstraint(
            constraint=c, status=ConstraintStatus.GROUNDED, realized_value=raw
        )
    meant = _plain(request.share_of(bound))
    return GroundedConstraint(
        constraint=c,
        status=ConstraintStatus.SUBSTITUTED,
        realized_value=raw,
        note=f"bound {_plain(bound)} means {request.direction} {meant}%",
    )


_HANDLERS = {
    ConstraintKind.DATA_TYPE: _ground_data_type,
    ConstraintKind.STATISTICAL_THRESHOLD: _ground_threshold,
    ConstraintKind.FOLD_CHANGE: _ground_fold_change,
    ConstraintKind.PERCENTILE: _ground_percentile,
}


def ground_constraints(
    constraints: list[Constraint],
    *,
    search_names: Collection[str],
    param_names: Collection[str],
    param_values: Mapping[str, str],
) -> list[GroundedConstraint]:
    """Ground each constraint against the realized strategy facts (the criteria's
    bound WDK search names, the union of their parameter names, and the values
    bound to them)."""
    realized = _RealizedSpec(
        search_names=list(search_names),
        param_names=frozenset(param_names),
        param_values=dict(param_values),
    )
    out: list[GroundedConstraint] = []
    for c in constraints:
        handler = _HANDLERS.get(c.kind)
        if handler is None:
            out.append(
                GroundedConstraint(constraint=c, status=ConstraintStatus.GROUNDED)
            )
        else:
            out.append(handler(c, realized))
    return out
