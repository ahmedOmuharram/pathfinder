"""An edit becomes the smallest batch of operations over the live graph.

Every step the edit does not name keeps its id, so the WDK step behind it
survives the turn.
"""

from __future__ import annotations

import pytest

from pathfinder.domain.parameters.values import MultiPickValue, NumberValue
from pathfinder.domain.strategy.ast import COMBINE_SEARCH_NAME, StrategyStepNode
from pathfinder.domain.strategy.graph_model import flatten_tree
from pathfinder.domain.strategy.operational_spec import (
    Criterion,
    OperationalSpec,
    SpecStructure,
    StructureNode,
)
from pathfinder.domain.strategy.operations import (
    AddCombineOp,
    AddLeafOp,
    AddTransformOp,
    DeleteResolution,
    DeleteStepOp,
    ReplaceSubtreeOp,
    UpdateCombineOperatorOp,
    UpdateStepParamsOp,
)
from pathfinder.domain.strategy.ops import CombineOp
from pathfinder.domain.strategy.session import StrategyGraph
from pathfinder.domain.strategy.spec_diff import diff_specs
from pathfinder.domain.strategy.spec_hydration import spec_from_ast
from pathfinder.domain.strategy.spec_to_operations import (
    UnsupportedEditError,
    operations_for,
)
from pathfinder.domain.strategy.strategy_ast import StrategyAst


def _text() -> StrategyStepNode:
    return StrategyStepNode(
        id="step_text",
        search_name="GenesByText",
        display_name="protease text",
        parameters={"organism": MultiPickValue(values=["Plasmodium"])},
    )


def _go() -> StrategyStepNode:
    return StrategyStepNode(
        id="step_go",
        search_name="GenesByGoTerm",
        display_name="proteolysis GO",
        parameters={"organism": MultiPickValue(values=["Plasmodium"])},
    )


def _expr() -> StrategyStepNode:
    return StrategyStepNode(
        id="step_expr",
        search_name="GenesByRNASeqEvidence",
        display_name="top decile",
        parameters={"min_expression_percentile": NumberValue(value=90)},
    )


def _combine(
    step_id: str,
    primary: StrategyStepNode,
    secondary: StrategyStepNode,
    operator: CombineOp = CombineOp.INTERSECT,
) -> StrategyStepNode:
    return StrategyStepNode(
        id=step_id,
        search_name=COMBINE_SEARCH_NAME,
        operator=operator,
        primary_input=primary,
        secondary_input=secondary,
    )


def _three_step_root() -> StrategyStepNode:
    return _combine("step_c2", _combine("step_c1", _text(), _go()), _expr())


def _graph_of(root: StrategyStepNode) -> StrategyGraph:
    graph = StrategyGraph(graph_id="g1", name="Test strategy", site_id="plasmodb")
    graph.record_type = "transcript"
    graph.steps = flatten_tree(root)
    graph.recompute_roots()
    graph.last_step_id = root.id
    return graph


def _spec_of(root: StrategyStepNode) -> OperationalSpec:
    ast = StrategyAst(record_type="transcript", root=root)
    return spec_from_ast(ast, goal="find proteases")


def _plan(
    before: OperationalSpec, after: OperationalSpec, graph: StrategyGraph
) -> list[object]:
    return list(
        operations_for(
            diff_specs(before, after), before=before, after=after, graph=graph
        )
    )


def test_operations_are_empty_when_the_diff_is_empty() -> None:
    root = _three_step_root()
    before = _spec_of(root)
    assert _plan(before, before.model_copy(deep=True), _graph_of(root)) == []


def test_kept_criterion_emits_no_operation() -> None:
    root = _three_step_root()
    before = _spec_of(root)
    after = before.model_copy(deep=True)
    for criterion in after.criteria:
        if criterion.id == "step_expr":
            criterion.resolved_params["min_expression_percentile"] = NumberValue(
                value=75
            )

    ops = _plan(before, after, _graph_of(root))

    assert [op.step_id for op in ops if isinstance(op, UpdateStepParamsOp)] == [
        "step_expr"
    ]
    assert len(ops) == 1


def test_changed_param_emits_update_step_params_on_the_same_step_id() -> None:
    root = _three_step_root()
    before = _spec_of(root)
    after = before.model_copy(deep=True)
    for criterion in after.criteria:
        if criterion.id == "step_go":
            criterion.resolved_params["organism"] = MultiPickValue(values=["P. vivax"])

    ops = _plan(before, after, _graph_of(root))

    assert len(ops) == 1
    op = ops[0]
    assert isinstance(op, UpdateStepParamsOp)
    assert op.step_id == "step_go"
    assert op.parameters["organism"] == MultiPickValue(values=["P. vivax"])


def test_a_changed_search_name_replaces_the_subtree_and_keeps_the_step_id() -> None:
    root = _three_step_root()
    before = _spec_of(root)
    after = before.model_copy(deep=True)
    for criterion in after.criteria:
        if criterion.id == "step_expr":
            criterion.search_name = "GenesByRNASeqSu"

    ops = _plan(before, after, _graph_of(root))

    assert len(ops) == 1
    op = ops[0]
    assert isinstance(op, ReplaceSubtreeOp)
    assert op.step_id == "step_expr"
    assert op.subtree.id == "step_expr"
    assert op.subtree.search_name == "GenesByRNASeqSu"


def test_a_dropped_param_replaces_the_subtree_rather_than_merging() -> None:
    """UpdateStepParamsOp merges, so a value the edit removes needs a replace."""
    root = _three_step_root()
    before = _spec_of(root)
    after = before.model_copy(deep=True)
    for criterion in after.criteria:
        if criterion.id == "step_expr":
            criterion.resolved_params = {}

    ops = _plan(before, after, _graph_of(root))

    assert len(ops) == 1
    op = ops[0]
    assert isinstance(op, ReplaceSubtreeOp)
    assert op.subtree.parameters == {}


def test_dropped_criterion_emits_delete_step_with_collapse() -> None:
    root = _three_step_root()
    before = _spec_of(root)
    after = _spec_of(_combine("step_c2", _text(), _expr()))
    # The reconstruction of the smaller tree renames nothing: the surviving
    # steps keep the ids the graph gave them.
    after.criteria = [c for c in before.criteria if c.id != "step_go"]
    after.structure = SpecStructure(
        root=StructureNode(
            kind="combine",
            operator=CombineOp.INTERSECT,
            inputs=[
                StructureNode(kind="leaf", criterion_id="step_text"),
                StructureNode(kind="leaf", criterion_id="step_expr"),
            ],
        )
    )

    ops = _plan(before, after, _graph_of(root))

    assert len(ops) == 1
    op = ops[0]
    assert isinstance(op, DeleteStepOp)
    assert op.step_id == "step_go"
    assert op.resolution is DeleteResolution.COLLAPSE_COMBINE


def test_added_transform_emits_add_transform_with_the_current_root_as_input() -> None:
    root = _three_step_root()
    before = _spec_of(root)
    after = before.model_copy(deep=True)
    after.criteria.append(
        Criterion(
            id="c_orthologs",
            text="map to P. vivax orthologs",
            search_name="GenesByOrthologs",
            role="transform",
            resolved_params={"organism": MultiPickValue(values=["P. vivax P01"])},
        )
    )
    assert before.structure is not None
    after.structure = SpecStructure(
        root=StructureNode(
            kind="transform",
            criterion_id="c_orthologs",
            inputs=[before.structure.root.model_copy(deep=True)],
        )
    )

    ops = _plan(before, after, _graph_of(root))

    assert len(ops) == 1
    op = ops[0]
    assert isinstance(op, AddTransformOp)
    assert op.input_id == "step_c2"
    assert op.mode == "new-root"
    assert op.step.id == "c_orthologs"
    assert op.step.search_name == "GenesByOrthologs"


def test_added_leaf_joins_the_current_root_with_the_declared_operator() -> None:
    root = _three_step_root()
    before = _spec_of(root)
    after = before.model_copy(deep=True)
    after.criteria.append(
        Criterion(
            id="c_secreted",
            text="predicted secreted",
            search_name="GenesBySignalPeptide",
        )
    )
    assert before.structure is not None
    after.structure = SpecStructure(
        root=StructureNode(
            kind="combine",
            operator=CombineOp.INTERSECT,
            inputs=[
                before.structure.root.model_copy(deep=True),
                StructureNode(kind="leaf", criterion_id="c_secreted"),
            ],
        )
    )

    ops = _plan(before, after, _graph_of(root))

    assert len(ops) == 2
    add_leaf, add_combine = ops
    assert isinstance(add_leaf, AddLeafOp)
    assert add_leaf.step.id == "c_secreted"
    assert isinstance(add_combine, AddCombineOp)
    assert add_combine.left_id == "step_c2"
    assert add_combine.right_id == "c_secreted"
    assert add_combine.step.operator is CombineOp.INTERSECT


def test_a_changed_combine_operator_updates_the_combine_in_place() -> None:
    root = _three_step_root()
    before = _spec_of(root)
    after = before.model_copy(deep=True)
    assert after.structure is not None
    after.structure.root.inputs[0].operator = CombineOp.UNION

    ops = _plan(before, after, _graph_of(root))

    assert len(ops) == 1
    op = ops[0]
    assert isinstance(op, UpdateCombineOperatorOp)
    assert op.step_id == "step_c1"
    assert op.operator is CombineOp.UNION


def test_a_rearrangement_of_the_steps_that_stay_is_refused() -> None:
    """Re-nesting the surviving steps has no in-place operation."""
    root = _three_step_root()
    before = _spec_of(root)
    after = before.model_copy(deep=True)
    after.structure = SpecStructure(
        root=StructureNode(
            kind="combine",
            operator=CombineOp.INTERSECT,
            inputs=[
                StructureNode(kind="leaf", criterion_id="step_text"),
                StructureNode(
                    kind="combine",
                    operator=CombineOp.INTERSECT,
                    inputs=[
                        StructureNode(kind="leaf", criterion_id="step_go"),
                        StructureNode(kind="leaf", criterion_id="step_expr"),
                    ],
                ),
            ],
        )
    )

    with pytest.raises(UnsupportedEditError):
        _plan(before, after, _graph_of(root))


def test_a_changed_criterion_that_names_no_step_is_refused() -> None:
    """A FRAME-authored label addresses nothing in the live graph."""
    root = _three_step_root()
    labelled = OperationalSpec(
        goal="find proteases",
        record_type="transcript",
        criteria=[
            Criterion(
                id="c1_protease_text",
                text="protease text",
                search_name="GenesByText",
                resolved_params={"organism": MultiPickValue(values=["Plasmodium"])},
            )
        ],
        structure=SpecStructure(
            root=StructureNode(kind="leaf", criterion_id="c1_protease_text")
        ),
    )
    after = labelled.model_copy(deep=True)
    after.criteria[0].resolved_params["organism"] = MultiPickValue(values=["P. vivax"])

    with pytest.raises(UnsupportedEditError):
        _plan(labelled, after, _graph_of(root))
