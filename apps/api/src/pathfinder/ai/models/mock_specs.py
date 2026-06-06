"""Canned strategy-plan specs for the deterministic test mock.

The mock's planning sub-agent emits one of these specs as a ``create_plan``
call plus a matching ``PlanDelta``. Kept separate from the routing logic in
``mock`` so each file stays within the per-file line budget.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class StepSpec:
    step_id: str
    search: str
    display: str
    step_type: str = "leaf"
    # (name, param_type, typed ParamValue)
    params: tuple[tuple[str, str, dict[str, Any]], ...] = ()


@dataclass(frozen=True)
class ConnSpec:
    from_step: str
    to_step: str
    input_type: str = "primary"
    operator: str | None = None


@dataclass(frozen=True)
class PlanSpec:
    title: str
    description: str
    rationale: str
    steps: tuple[StepSpec, ...]
    connections: tuple[ConnSpec, ...] = field(default_factory=tuple)


PLASMO_SPEC = PlanSpec(
    title="Plasmodium falciparum genes (mock)",
    description="Single-step strategy returning all Plasmodium falciparum 3D7 genes.",
    rationale="GenesByTaxon scoped to P. falciparum 3D7 returns the full gene set.",
    steps=(
        StepSpec(
            step_id="pf_genes",
            search="GenesByTaxon",
            display="Plasmodium falciparum genes",
            params=(
                (
                    "organism",
                    "multi-pick-vocabulary",
                    {
                        "type": "multi-pick-vocabulary",
                        "values": ["Plasmodium falciparum 3D7"],
                    },
                ),
            ),
        ),
    ),
)

TEXT_SPEC = PlanSpec(
    title="Kinase genes (mock)",
    description="Single-step strategy returning genes whose product mentions kinase.",
    rationale="GenesByText on 'kinase' is valid on every VEuPathDB site.",
    steps=(
        StepSpec(
            step_id="kinase_genes",
            search="GenesByText",
            display="Kinase genes",
            params=(
                ("text_expression", "string", {"type": "string", "value": "kinase"}),
                (
                    "text_fields",
                    "multi-pick-vocabulary",
                    {"type": "multi-pick-vocabulary", "values": ["product"]},
                ),
                ("document_type", "string", {"type": "string", "value": "gene"}),
            ),
        ),
    ),
)


def _text_leaf(step_id: str, display: str, expression: str) -> StepSpec:
    return StepSpec(
        step_id=step_id,
        search="GenesByText",
        display=display,
        params=(
            ("text_expression", "string", {"type": "string", "value": expression}),
            (
                "text_fields",
                "multi-pick-vocabulary",
                {"type": "multi-pick-vocabulary", "values": ["product"]},
            ),
            ("document_type", "string", {"type": "string", "value": "gene"}),
            (
                "text_search_organism",
                "multi-pick-vocabulary",
                {
                    "type": "multi-pick-vocabulary",
                    "values": ["Plasmodium falciparum 3D7"],
                },
            ),
        ),
    )


# Two text leaves combined with UNION; the combine step id ``interpro_or_go``
# is what the drug-targets journey addresses in the graph to flip the operator.
INTERPRO_SPEC = PlanSpec(
    title="Candidate kinase drug targets (mock)",
    description=(
        "Kinases identified via InterPro PF00069 (Pkinase) unioned with "
        "EC 2.7.-.- phosphotransferases."
    ),
    rationale=(
        "Broadening kinase identification across InterPro PF00069 and EC "
        "2.7.-.- maximises candidate recall before downstream filters."
    ),
    steps=(
        _text_leaf(
            "interpro_kinases",
            "Kinases via InterPro PF00069 (Pkinase domain)",
            "kinase",
        ),
        _text_leaf(
            "ec_kinases",
            "Kinases via EC 2.7.-.- (phosphotransferases)",
            "phosphotransferase",
        ),
        StepSpec(
            step_id="interpro_or_go",
            search="__combine__",
            display="InterPro PF00069 OR EC 2.7 kinases",
            step_type="combine",
        ),
    ),
    connections=(
        ConnSpec(from_step="interpro_kinases", to_step="interpro_or_go"),
        ConnSpec(
            from_step="ec_kinases",
            to_step="interpro_or_go",
            input_type="secondary",
            operator="UNION",
        ),
    ),
)


def create_plan_args(spec: PlanSpec) -> dict[str, Any]:
    return {
        "title": spec.title,
        "description": spec.description,
        "rationale": spec.rationale,
        "steps": [
            {
                "id": step.step_id,
                "search_name": step.search,
                "display_name": step.display,
                "record_type": "transcript",
                "rationale": "",
                "step_type": step.step_type,
                "parameters": {name: value for name, _kind, value in step.params},
            }
            for step in spec.steps
        ],
        "connections": [
            {
                "from_step": conn.from_step,
                "to_step": conn.to_step,
                "input_type": conn.input_type,
                "operator": conn.operator,
            }
            for conn in spec.connections
        ],
    }


def _planned_param(name: str, kind: str, value: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "displayName": name.replace("_", " ").title(),
        "paramType": kind,
        "value": value,
        "status": "set",
        "required": True,
    }


def plan_delta(spec: PlanSpec) -> dict[str, Any]:
    return {
        "plan": {
            "title": spec.title,
            "description": spec.description,
            "rationale": spec.rationale,
            "steps": [
                {
                    "id": step.step_id,
                    "searchName": step.search,
                    "displayName": step.display,
                    "recordType": "transcript",
                    "rationale": "",
                    "stepType": step.step_type,
                    "status": "ready",
                    "operator": "UNION" if step.step_type == "combine" else None,
                    "parameters": [
                        _planned_param(name, kind, value)
                        for name, kind, value in step.params
                    ],
                }
                for step in spec.steps
            ],
            "connections": [
                {
                    "fromStep": conn.from_step,
                    "toStep": conn.to_step,
                    "inputType": conn.input_type,
                    "operator": conn.operator,
                }
                for conn in spec.connections
            ],
        },
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
