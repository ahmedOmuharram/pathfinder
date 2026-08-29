"""After a build, a criterion addresses the step the build produced.

FRAME names a criterion with a label. The build mints a step id for it. Unless
the spec adopts that id, the next turn's edit has nothing to address.
"""

from __future__ import annotations

from pathfinder.domain.parameters.values import MultiPickValue
from pathfinder.domain.strategy.graph_model import flatten_tree
from pathfinder.domain.strategy.operational_spec import (
    Criterion,
    OperationalSpec,
    SpecStructure,
    StructureNode,
    build_step_tree,
    renumber_criteria,
)
from pathfinder.domain.strategy.ops import CombineOp


def _spec() -> OperationalSpec:
    return OperationalSpec(
        goal="proteases",
        record_type="transcript",
        criteria=[
            Criterion(
                id="c1_protease_text",
                text="protease text",
                search_name="GenesByText",
                role="seed",
                resolved_params={"organism": MultiPickValue(values=["Plasmodium"])},
            ),
            Criterion(
                id="c2_go",
                text="proteolysis GO",
                search_name="GenesByGoTerm",
            ),
            Criterion(
                id="c3_orthologs",
                text="P. vivax orthologs",
                search_name="GenesByOrthologs",
                role="transform",
            ),
        ],
        structure=SpecStructure(
            root=StructureNode(
                kind="transform",
                criterion_id="c3_orthologs",
                inputs=[
                    StructureNode(
                        kind="combine",
                        operator=CombineOp.INTERSECT,
                        inputs=[
                            StructureNode(kind="leaf", criterion_id="c1_protease_text"),
                            StructureNode(kind="leaf", criterion_id="c2_go"),
                        ],
                    )
                ],
            )
        ),
    )


def test_the_build_reports_the_step_id_it_minted_for_each_criterion() -> None:
    built = build_step_tree(_spec())

    assert set(built.step_id_by_criterion) == {
        "c1_protease_text",
        "c2_go",
        "c3_orthologs",
    }
    step_ids = set(flatten_tree(built.root))
    assert set(built.step_id_by_criterion.values()) <= step_ids


def test_a_built_spec_addresses_its_steps_by_step_id() -> None:
    spec = _spec()
    built = build_step_tree(spec)

    renumbered = renumber_criteria(spec, built.step_id_by_criterion)

    assert {c.id for c in renumbered.criteria} == set(
        built.step_id_by_criterion.values()
    )
    assert renumbered.structure is not None
    assert (
        renumbered.structure.root.criterion_id
        == built.step_id_by_criterion["c3_orthologs"]
    )
    combine = renumbered.structure.root.inputs[0]
    assert [node.criterion_id for node in combine.inputs] == [
        built.step_id_by_criterion["c1_protease_text"],
        built.step_id_by_criterion["c2_go"],
    ]


def test_renumbering_keeps_every_bound_value() -> None:
    spec = _spec()
    built = build_step_tree(spec)

    renumbered = renumber_criteria(spec, built.step_id_by_criterion)

    seed = renumbered.criteria[0]
    assert seed.search_name == "GenesByText"
    assert seed.resolved_params == {"organism": MultiPickValue(values=["Plasmodium"])}


def test_a_criterion_the_build_did_not_place_keeps_its_id() -> None:
    spec = _spec()
    spec.criteria.append(Criterion(id="c4_unused", text="unused", search_name="X"))

    renumbered = renumber_criteria(spec, build_step_tree(spec).step_id_by_criterion)

    assert "c4_unused" in {c.id for c in renumbered.criteria}
