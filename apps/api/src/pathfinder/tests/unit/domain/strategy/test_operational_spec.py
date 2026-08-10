from __future__ import annotations

import pytest

from pathfinder.domain.parameters.values import MultiPickValue
from pathfinder.domain.strategy.ast import COMBINE_SEARCH_NAME
from pathfinder.domain.strategy.operational_spec import (
    Criterion,
    OpenSlot,
    OperationalSpec,
    SpecStructure,
    StructureNode,
    operational_spec_to_step_tree,
)
from pathfinder.domain.strategy.ops import CombineOp

_PF = MultiPickValue(values=["Plasmodium falciparum 3D7"])


def _bound(cid: str, search: str) -> Criterion:
    return Criterion(
        id=cid, text="t", search_name=search, resolved_params={"organism": _PF}
    )


def _leaf_spec() -> OperationalSpec:
    return OperationalSpec(
        goal="g",
        criteria=[_bound("c1", "GenesWithSignalPeptide")],
        structure=SpecStructure(root=StructureNode(kind="leaf", criterion_id="c1")),
    )


def test_transform_node_builds_a_transform_step_with_primary_input() -> None:
    # A transform criterion (e.g. GenesByOrthologs mapping one organism's genes
    # to another's) applies its search to an INPUT subtree — it must materialize
    # as a WDK transform step (search + primary_input), NOT a standalone leaf
    # (which WDK rejects for an input-step search).
    spec = OperationalSpec(
        goal="g",
        criteria=[
            _bound("c_seed", "GenesByRNASeqGametocytes"),
            _bound("c_ortho", "GenesByOrthologs"),
        ],
        structure=SpecStructure(
            root=StructureNode(
                kind="transform",
                criterion_id="c_ortho",
                inputs=[StructureNode(kind="leaf", criterion_id="c_seed")],
            )
        ),
    )
    tree = operational_spec_to_step_tree(spec)
    assert tree.infer_kind() == "transform"
    assert tree.search_name == "GenesByOrthologs"
    assert tree.secondary_input is None
    assert tree.primary_input is not None
    assert tree.primary_input.search_name == "GenesByRNASeqGametocytes"


def test_criterion_bound_flag() -> None:
    assert Criterion(id="c1", text="t").bound is False
    assert _bound("c1", "GenesWithSignalPeptide").bound is True


def test_ready_to_build_transitions() -> None:
    assert _leaf_spec().ready_to_build is True
    # unbound criterion blocks
    assert (
        OperationalSpec(
            goal="g",
            criteria=[Criterion(id="c1", text="t")],
            structure=SpecStructure(root=StructureNode(kind="leaf", criterion_id="c1")),
        ).ready_to_build
        is False
    )
    # open slot blocks
    assert (
        OperationalSpec(
            goal="g",
            criteria=[_bound("c1", "S")],
            structure=SpecStructure(root=StructureNode(kind="leaf", criterion_id="c1")),
            open_slots=[OpenSlot(criterion_id="c1", param_name="x")],
        ).ready_to_build
        is False
    )
    # no structure blocks
    assert (
        OperationalSpec(goal="g", criteria=[_bound("c1", "S")]).ready_to_build is False
    )


def test_seam_single_leaf() -> None:
    node = operational_spec_to_step_tree(_leaf_spec())
    assert node.search_name == "GenesWithSignalPeptide"
    assert node.parameters["organism"] == _PF
    assert node.primary_input is None


def test_seam_two_leaf_intersect() -> None:
    spec = OperationalSpec(
        goal="g",
        criteria=[
            _bound("c1", "GenesWithSignalPeptide"),
            _bound("c2", "GenesByTransmembraneDomains"),
        ],
        structure=SpecStructure(
            root=StructureNode(
                kind="combine",
                operator=CombineOp.INTERSECT,
                inputs=[
                    StructureNode(kind="leaf", criterion_id="c1"),
                    StructureNode(kind="leaf", criterion_id="c2"),
                ],
            )
        ),
    )
    node = operational_spec_to_step_tree(spec)
    assert node.search_name == COMBINE_SEARCH_NAME
    assert node.operator == CombineOp.INTERSECT
    assert node.primary_input is not None
    assert node.secondary_input is not None
    assert node.primary_input.search_name == "GenesWithSignalPeptide"
    assert node.secondary_input.search_name == "GenesByTransmembraneDomains"


def test_seam_three_leaf_left_fold() -> None:
    crits = [_bound(f"c{i}", f"S{i}") for i in (1, 2, 3)]
    spec = OperationalSpec(
        goal="g",
        criteria=crits,
        structure=SpecStructure(
            root=StructureNode(
                kind="combine",
                operator=CombineOp.UNION,
                inputs=[
                    StructureNode(kind="leaf", criterion_id=f"c{i}") for i in (1, 2, 3)
                ],
            )
        ),
    )
    node = operational_spec_to_step_tree(spec)
    # left fold: ((S1 UNION S2) UNION S3)
    assert node.secondary_input is not None
    assert node.secondary_input.search_name == "S3"
    assert node.primary_input is not None
    assert node.primary_input.search_name == COMBINE_SEARCH_NAME


def test_seam_unbound_criterion_raises() -> None:
    spec = OperationalSpec(
        goal="g",
        criteria=[Criterion(id="c1", text="t")],
        structure=SpecStructure(root=StructureNode(kind="leaf", criterion_id="c1")),
    )
    with pytest.raises(ValueError, match="unbound"):
        operational_spec_to_step_tree(spec)


class TestNestedBranchesReachWdk:
    """A UNION branch on the secondary input must survive to the step tree.

    WDK step trees carry a primary and a secondary input, so
    ``A INTERSECT (B UNION C)`` is representable. Flattening it to
    ``(A INTERSECT B) UNION C`` asks a different question and would silently
    change the science. FRAME's set_structure used to left-fold, which made
    the nested form unreachable; the seam itself was always general, and
    this pins that.
    """

    def _spec(self) -> OperationalSpec:
        return OperationalSpec(
            goal="drug targets",
            criteria=[
                Criterion(id="kinases", text="kinases", search_name="GenesByInterpro"),
                Criterion(id="ms", text="mass spec", search_name="GenesByMassSpec"),
                Criterion(id="derisi", text="derisi", search_name="GenesByMicroarray"),
            ],
            structure=SpecStructure(
                root=StructureNode(
                    kind="combine",
                    operator=CombineOp.INTERSECT,
                    inputs=[
                        StructureNode(kind="leaf", criterion_id="kinases"),
                        StructureNode(
                            kind="combine",
                            operator=CombineOp.UNION,
                            inputs=[
                                StructureNode(kind="leaf", criterion_id="ms"),
                                StructureNode(kind="leaf", criterion_id="derisi"),
                            ],
                        ),
                    ],
                )
            ),
        )

    def test_the_union_stays_on_the_secondary_input(self) -> None:
        root = operational_spec_to_step_tree(self._spec())

        assert root.operator == CombineOp.INTERSECT
        branch = root.secondary_input
        assert branch is not None
        assert branch.operator == CombineOp.UNION

    def test_the_branch_keeps_both_of_its_own_leaves(self) -> None:
        root = operational_spec_to_step_tree(self._spec())
        branch = root.secondary_input
        assert branch is not None

        assert branch.primary_input is not None
        assert branch.secondary_input is not None
        assert branch.primary_input.search_name == "GenesByMassSpec"
        assert branch.secondary_input.search_name == "GenesByMicroarray"

    def test_the_intersect_side_is_not_rewritten(self) -> None:
        root = operational_spec_to_step_tree(self._spec())

        assert root.primary_input is not None
        assert root.primary_input.search_name == "GenesByInterpro"
