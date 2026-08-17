"""Canned FRAME specs for the deterministic test mock.

The mock's FRAME sub-agent drives ``set_criterion`` twice per criterion (once
with no ``params`` to read the sheet, once to propose them) + ``set_structure``
to assemble an ``OperationalSpec``, then returns a ``FrameResult``.
Every visible parameter is proposed here and validated against
the real WDK vocabulary, so the canned criteria use one search whose sheet is
one organism parameter (``GenesByTaxon``). The mock exercises the
FRAME/BUILD/VERIFY mechanics, not real biology.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from pydantic_ai.messages import ToolCallPart

_PF_3D7 = "Plasmodium falciparum 3D7"


@dataclass(frozen=True)
class CriterionSpec:
    criterion_id: str
    text: str
    search_name: str
    role: str = "filter"
    # A value or null for every visible parameter of the search.
    params: tuple[tuple[str, str | list[str] | None], ...] = ()


@dataclass(frozen=True)
class SpecPlan:
    title: str
    criteria: tuple[CriterionSpec, ...]
    # The operator that combines the criteria, left to right. One criterion
    # needs none.
    operator: str | None = None


# Single GenesByTaxon leaf — organism resolves cleanly on plasmo sites.
SINGLE_SPEC = SpecPlan(
    title="Plasmodium falciparum genes (mock)",
    criteria=(
        CriterionSpec(
            criterion_id="c1",
            text=f"{_PF_3D7} genes",
            search_name="GenesByTaxon",
            role="seed",
            params=(("organism", [_PF_3D7]),),
        ),
    ),
)

# Two GenesByTaxon leaves combined with UNION — a multi-node tree that still
# resolves cleanly (both sides are organism-scoped taxon searches).
COMBINED_SPEC = SpecPlan(
    title="Combined Plasmodium genes (mock)",
    criteria=(
        CriterionSpec(
            criterion_id="c1",
            text=f"{_PF_3D7} genes",
            search_name="GenesByTaxon",
            role="seed",
            params=(("organism", [_PF_3D7]),),
        ),
        CriterionSpec(
            criterion_id="c2",
            text="Plasmodium falciparum genes",
            search_name="GenesByTaxon",
            role="filter",
            params=(("organism", ["Plasmodium falciparum"]),),
        ),
    ),
    operator="UNION",
)


def _call(name: str, args: dict[str, Any]) -> ToolCallPart:
    return ToolCallPart(
        tool_name=name,
        args=args,
        tool_call_id=f"mock_{name}_{uuid4().hex[:10]}",
    )


def set_criterion_args(crit: CriterionSpec, *, with_params: bool) -> dict[str, Any]:
    """The sheet-reading call carries no ``params``; the proposal carries them."""
    args: dict[str, Any] = {
        "criterion_id": crit.criterion_id,
        "text": crit.text,
        "search_name": crit.search_name,
        "role": crit.role,
    }
    if with_params:
        args["params"] = dict(crit.params)
    return args


def _leaf(crit: CriterionSpec) -> dict[str, Any]:
    return {"kind": "leaf", "criterionId": crit.criterion_id}


def set_structure_args(spec: SpecPlan) -> dict[str, Any]:
    """``set_structure`` takes a tree. One criterion is a leaf; several fold
    left under the plan's operator."""
    root = _leaf(spec.criteria[0])
    for crit in spec.criteria[1:]:
        root = {
            "kind": "combine",
            "operator": spec.operator,
            "inputs": [root, _leaf(crit)],
        }
    return {"root": root}


def _criterion_ids_called(
    prior: list[ToolCallPart], *, with_params: bool
) -> set[object]:
    return {
        c.args_as_dict().get("criterion_id")
        for c in prior
        if c.tool_name == "set_criterion"
        and ("params" in c.args_as_dict()) is with_params
    }


def frame_call(
    spec: SpecPlan, already_called: list[ToolCallPart] | None = None
) -> ToolCallPart:
    """Next FRAME tool call: each criterion reads its sheet then proposes its
    params, then ``set_structure``, then the ``FrameResult`` via ``final_result``."""
    prior = already_called or []
    called = {c.tool_name: c for c in prior}
    read_sheet = _criterion_ids_called(prior, with_params=False)
    proposed = _criterion_ids_called(prior, with_params=True)
    for crit in spec.criteria:
        if crit.criterion_id not in read_sheet:
            return _call("set_criterion", set_criterion_args(crit, with_params=False))
        if crit.criterion_id not in proposed:
            return _call("set_criterion", set_criterion_args(crit, with_params=True))
    if "set_structure" not in called:
        return _call("set_structure", set_structure_args(spec))
    return _call("final_result", frame_result(spec))


def frame_result(spec: SpecPlan) -> dict[str, Any]:
    return {
        "summary": f"Framed {len(spec.criteria)} criterion(s) for {spec.title}.",
        "disposition": "spec_ready",
        "openQuestions": [],
    }


def verification_delta(*, success: bool) -> dict[str, Any]:
    return {
        "digest": {
            "disposition": "done" if success else "awaiting_user",
            "prose": "[mock] verification digest.",
            "reason": "mock verification",
            "success": success,
        },
    }
