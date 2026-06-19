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


GO_SPEC = PlanSpec(
    title="Protein kinase GO genes (mock)",
    description="P. falciparum 3D7 genes annotated with protein kinase activity.",
    rationale="GenesByGoTerm on GO:0004672 with curated+computed evidence.",
    steps=(
        StepSpec(
            step_id="go_kinases",
            search="GenesByGoTerm",
            display="Protein kinase GO genes",
            params=(
                (
                    "organism",
                    "multi-pick-vocabulary",
                    {
                        "type": "multi-pick-vocabulary",
                        "values": ["Plasmodium falciparum 3D7"],
                    },
                ),
                (
                    "go_term_evidence",
                    "multi-pick-vocabulary",
                    {
                        "type": "multi-pick-vocabulary",
                        "values": ["Curated", "Computed"],
                    },
                ),
                (
                    "go_term_slim",
                    "single-pick-vocabulary",
                    {"type": "single-pick-vocabulary", "value": "No"},
                ),
                (
                    "go_typeahead",
                    "multi-pick-vocabulary",
                    {"type": "multi-pick-vocabulary", "values": ["GO:0004672"]},
                ),
                ("go_term", "string", {"type": "string", "value": "GO:0004672"}),
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


def _go_leaf(step_id: str, display: str) -> StepSpec:
    return StepSpec(
        step_id=step_id,
        search="GenesByGoTerm",
        display=display,
        params=(
            (
                "organism",
                "multi-pick-vocabulary",
                {
                    "type": "multi-pick-vocabulary",
                    "values": ["Plasmodium falciparum 3D7"],
                },
            ),
            (
                "go_term_evidence",
                "multi-pick-vocabulary",
                {"type": "multi-pick-vocabulary", "values": ["Curated", "Computed"]},
            ),
            (
                "go_term_slim",
                "single-pick-vocabulary",
                {"type": "single-pick-vocabulary", "value": "No"},
            ),
            (
                "go_typeahead",
                "multi-pick-vocabulary",
                {"type": "multi-pick-vocabulary", "values": ["GO:0004672"]},
            ),
            ("go_term", "string", {"type": "string", "value": "GO:0004672"}),
        ),
    )


COMPREHENSIVE_SPEC = PlanSpec(
    title="Comprehensive kinase candidate strategy (mock)",
    description=(
        "Text kinases UNION GO protein-kinase genes, INTERSECT P. falciparum "
        "3D7 — exercises string, multi-pick, tree, single-pick and typeahead "
        "params across a 5-step tree."
    ),
    rationale="Multi-search candidate set spanning every parameter widget.",
    steps=(
        _text_leaf("text_kinases", "Text kinases", "kinase"),
        _go_leaf("go_kinase_genes", "GO protein-kinase genes"),
        StepSpec(
            step_id="pf_taxon",
            search="GenesByTaxon",
            display="P. falciparum 3D7 genes",
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
        StepSpec(
            step_id="text_or_go",
            search="__combine__",
            display="Text OR GO kinases",
            step_type="combine",
        ),
        StepSpec(
            step_id="narrowed",
            search="__combine__",
            display="Narrowed to P. falciparum 3D7",
            step_type="combine",
        ),
    ),
    connections=(
        ConnSpec(from_step="text_kinases", to_step="text_or_go"),
        ConnSpec(
            from_step="go_kinase_genes",
            to_step="text_or_go",
            input_type="secondary",
            operator="UNION",
        ),
        ConnSpec(from_step="text_or_go", to_step="narrowed"),
        ConnSpec(
            from_step="pf_taxon",
            to_step="narrowed",
            input_type="secondary",
            operator="INTERSECT",
        ),
    ),
)


def _step_arg(step: StepSpec, spec: PlanSpec) -> dict[str, Any]:
    # create_plan derives connections from each combine step's left_id/right_id
    # (there is no top-level connections list anymore). A combine step takes an
    # empty search_name so the tool normalizes it to the combine search.
    arg: dict[str, Any] = {
        "id": step.step_id,
        "search_name": "" if step.step_type == "combine" else step.search,
        "display_name": step.display,
        "record_type": "transcript",
        "rationale": "",
        "step_type": step.step_type,
        "parameters": {name: value for name, _kind, value in step.params},
    }
    if step.step_type == "combine":
        incoming = [c for c in spec.connections if c.to_step == step.step_id]
        primary = next((c for c in incoming if c.input_type == "primary"), None)
        secondary = next((c for c in incoming if c.input_type == "secondary"), None)
        if primary is not None:
            arg["left_id"] = primary.from_step
        if secondary is not None:
            arg["right_id"] = secondary.from_step
            arg["operator"] = secondary.operator
    return arg


def create_plan_args(spec: PlanSpec) -> dict[str, Any]:
    return {
        "title": spec.title,
        "description": spec.description,
        "rationale": spec.rationale,
        "steps": [_step_arg(step, spec) for step in spec.steps],
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
