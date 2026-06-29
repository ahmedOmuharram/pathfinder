"""Canned FRAME specs for the deterministic test mock.

The mock's FRAME sub-agent drives ``set_criterion`` (one per criterion) +
``set_structure`` to assemble an ``OperationalSpec``, then returns a
``FrameResult``. Params are resolved by the real WDK-backed resolver, so the
canned criteria use searches whose params auto-resolve from intent
(``GenesByTaxon`` scoped by organism) — the mock exercises the FRAME→BUILD→
VERIFY mechanics, not real biology.
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
    organism_scope: str | None = None


@dataclass(frozen=True)
class SpecPlan:
    title: str
    criteria: tuple[CriterionSpec, ...]
    # left-fold combine operators; ``len(criteria) - 1`` entries.
    operators: tuple[str, ...] = ()


# Single GenesByTaxon leaf — organism resolves cleanly on plasmo sites.
SINGLE_SPEC = SpecPlan(
    title="Plasmodium falciparum genes (mock)",
    criteria=(
        CriterionSpec(
            criterion_id="c1",
            text=f"{_PF_3D7} genes",
            search_name="GenesByTaxon",
            role="seed",
            organism_scope=_PF_3D7,
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
            organism_scope=_PF_3D7,
        ),
        CriterionSpec(
            criterion_id="c2",
            text="Plasmodium falciparum genes",
            search_name="GenesByTaxon",
            role="filter",
            organism_scope="Plasmodium falciparum",
        ),
    ),
    operators=("UNION",),
)


def _call(name: str, args: dict[str, Any]) -> ToolCallPart:
    return ToolCallPart(
        tool_name=name,
        args=args,
        tool_call_id=f"mock_{name}_{uuid4().hex[:10]}",
    )


def set_criterion_args(crit: CriterionSpec) -> dict[str, Any]:
    args: dict[str, Any] = {
        "criterion_id": crit.criterion_id,
        "text": crit.text,
        "search_name": crit.search_name,
        "role": crit.role,
    }
    if crit.organism_scope is not None:
        args["organism_scope"] = crit.organism_scope
    return args


def set_structure_args(spec: SpecPlan) -> dict[str, Any]:
    return {
        "criterion_ids": [c.criterion_id for c in spec.criteria],
        "operators": list(spec.operators),
    }


def frame_call(
    spec: SpecPlan, already_called: list[ToolCallPart] | None = None
) -> ToolCallPart:
    """Next FRAME tool call: each unbound ``set_criterion`` in order, then
    ``set_structure``, then the ``FrameResult`` via ``final_result``."""
    called = {c.tool_name: c for c in (already_called or [])}
    called_criterion_ids = {
        c.args_as_dict().get("criterion_id")
        for c in (already_called or [])
        if c.tool_name == "set_criterion"
    }
    for crit in spec.criteria:
        if crit.criterion_id not in called_criterion_ids:
            return _call("set_criterion", set_criterion_args(crit))
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
