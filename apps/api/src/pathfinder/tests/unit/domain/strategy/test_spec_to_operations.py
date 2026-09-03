"""An edit becomes the smallest batch of operations over the live graph.

Every step the edit does not name keeps its id, so the WDK step behind it
survives the turn.
"""

from __future__ import annotations

import pytest

from pathfinder.domain.parameters.values import MultiPickValue, NumberValue
from pathfinder.domain.strategy.ast import COMBINE_SEARCH_NAME, StrategyStepNode
from pathfinder.domain.strategy.graph_model import (
    StepKind,
    StrategyStep,
    flatten_tree,
)
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
    GraphOperation,
    ReplaceSubtreeOp,
    UpdateCombineOperatorOp,
    UpdateStepParamsOp,
)
from pathfinder.domain.strategy.operations.apply import apply_operation
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


def _tm() -> StrategyStepNode:
    return StrategyStepNode(
        id="step_tm",
        search_name="GenesByTransmembraneDomains",
        display_name="two or more TM domains",
        parameters={"min_tm": NumberValue(value=2)},
    )


def _transform_over(node: StrategyStepNode) -> StrategyStepNode:
    return StrategyStepNode(
        id="step_orth",
        search_name="GenesByOrthologs",
        display_name="P. vivax orthologs",
        parameters={"organism": MultiPickValue(values=["P. vivax P01"])},
        primary_input=node,
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
) -> list[GraphOperation]:
    return list(
        operations_for(
            diff_specs(before, after), before=before, after=after, graph=graph
        )
    )


def _applied(root: StrategyStepNode, ops: list[GraphOperation]) -> StrategyGraph:
    """The live graph after the plan is applied to it."""
    graph = _graph_of(root)
    for op in ops:
        apply_operation(graph, op)
    return graph


def _shape(graph: StrategyGraph) -> str:
    """The boolean shape of the primary tree, naming only non-combine steps."""

    def render(step_id: str) -> str:
        step = graph.steps[step_id]
        if step.kind is StepKind.COMBINE:
            left, right = step.inputs()
            return f"({render(left)} {step.operator} {render(right)})"
        if step.primary_input_id is not None:
            return f"{step_id}[{render(step.primary_input_id)}]"
        return step_id

    root_id = graph.primary_root_id()
    assert root_id is not None
    return render(root_id)


def _leaf(criterion_id: str) -> StructureNode:
    return StructureNode(kind="leaf", criterion_id=criterion_id)


def _joined(operator: CombineOp, *inputs: StructureNode) -> StructureNode:
    return StructureNode(kind="combine", operator=operator, inputs=list(inputs))


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


def _rearranged(root: StrategyStepNode) -> OperationalSpec:
    """The same three criteria, nested as ``text AND (go AND expr)``."""
    after = _spec_of(root).model_copy(deep=True)
    after.structure = SpecStructure(
        root=_joined(
            CombineOp.INTERSECT,
            _leaf("step_text"),
            _joined(CombineOp.INTERSECT, _leaf("step_go"), _leaf("step_expr")),
        )
    )
    return after


def test_a_rearrangement_of_the_steps_that_stay_replaces_the_combines() -> None:
    """Re-nesting the surviving steps is one replacement above the leaves."""
    root = _three_step_root()
    before = _spec_of(root)

    ops = _plan(before, _rearranged(root), _graph_of(root))

    assert len(ops) == 1
    op = ops[0]
    assert isinstance(op, ReplaceSubtreeOp)
    assert op.step_id == "step_c2"
    assert (
        _shape(_applied(root, ops))
        == "(step_text INTERSECT (step_go INTERSECT step_expr))"
    )


def test_a_rearrangement_keeps_every_leaf_step_id() -> None:
    """A leaf keeps its id, so the WDK step and the revision behind it survive."""
    root = _three_step_root()
    before = _spec_of(root)

    ops = _plan(before, _rearranged(root), _graph_of(root))
    graph = _applied(root, ops)

    assert {"step_text", "step_go", "step_expr"} <= set(graph.steps)
    assert not [op for op in ops if isinstance(op, (AddLeafOp, DeleteStepOp))]


def test_a_rearrangement_reuses_the_combine_whose_inputs_do_not_move() -> None:
    """A combine over an unchanged ordered pair keeps its id and its WDK step."""
    text_and_go = _combine("step_c1", _text(), _go())
    expr_and_tm = _combine("step_c2", _expr(), _tm())
    root = _combine("step_c3", text_and_go, expr_and_tm)
    before = _spec_of(root)
    after = before.model_copy(deep=True)
    after.structure = SpecStructure(
        root=_joined(
            CombineOp.UNION,
            _joined(CombineOp.INTERSECT, _leaf("step_text"), _leaf("step_go")),
            _joined(CombineOp.INTERSECT, _leaf("step_tm"), _leaf("step_expr")),
        )
    )

    graph = _applied(root, _plan(before, after, _graph_of(root)))

    assert graph.steps["step_c1"].primary_input_id == "step_text"
    assert graph.steps["step_c1"].secondary_input_id == "step_go"
    assert "step_c2" not in graph.steps
    assert _shape(graph) == (
        "((step_text INTERSECT step_go) UNION (step_tm INTERSECT step_expr))"
    )


def test_a_rearrangement_that_drops_a_surviving_leaf_is_refused() -> None:
    """A criterion the edit keeps must hold a position in the new shape."""
    root = _three_step_root()
    before = _spec_of(root)
    after = before.model_copy(deep=True)
    after.structure = SpecStructure(
        root=_joined(CombineOp.INTERSECT, _leaf("step_text"), _leaf("step_go"))
    )

    with pytest.raises(UnsupportedEditError) as excinfo:
        _plan(before, after, _graph_of(root))

    assert "step_expr" in str(excinfo.value)


def test_a_rearrangement_that_names_a_step_the_graph_lacks_is_refused() -> None:
    """A rewire mints no step for a criterion the strategy never held."""
    root = _three_step_root()
    before = _spec_of(root)
    before.criteria.append(
        Criterion(id="step_ghost", text="never built", search_name="GenesByTaxon")
    )
    after = before.model_copy(deep=True)
    after.structure = SpecStructure(
        root=_joined(
            CombineOp.INTERSECT,
            _leaf("step_ghost"),
            _joined(
                CombineOp.INTERSECT,
                _leaf("step_text"),
                _joined(CombineOp.INTERSECT, _leaf("step_go"), _leaf("step_expr")),
            ),
        )
    )

    with pytest.raises(UnsupportedEditError) as excinfo:
        _plan(before, after, _graph_of(root))

    assert "step_ghost" in str(excinfo.value)


def test_a_rearrangement_that_adopts_a_step_from_outside_is_refused() -> None:
    """An edit rewires the strategy's own steps and adopts no stray."""
    root = _three_step_root()
    graph = _graph_of(root)
    graph.steps["step_stray"] = StrategyStep(
        id="step_stray", kind=StepKind.SEARCH, search_name="GenesByTaxon"
    )
    graph.recompute_roots()
    before = _spec_of(root)
    after = before.model_copy(deep=True)
    after.criteria.append(
        Criterion(id="step_stray", text="a detached step", search_name="GenesByTaxon")
    )
    after.structure = SpecStructure(
        root=_joined(
            CombineOp.INTERSECT,
            _leaf("step_stray"),
            _joined(
                CombineOp.INTERSECT,
                _leaf("step_text"),
                _joined(CombineOp.INTERSECT, _leaf("step_go"), _leaf("step_expr")),
            ),
        )
    )

    with pytest.raises(UnsupportedEditError) as excinfo:
        _plan(before, after, graph)

    assert "step_stray" in str(excinfo.value)


def test_a_moved_transform_is_rewired_and_keeps_its_step_id() -> None:
    """The structure states the transform's input, so the edit may move it."""
    root = _transform_over(_combine("step_c1", _text(), _go()))
    before = _spec_of(root)
    after = before.model_copy(deep=True)
    after.structure = SpecStructure(
        root=_joined(
            CombineOp.INTERSECT,
            StructureNode(
                kind="transform",
                criterion_id="step_orth",
                inputs=[_leaf("step_text")],
            ),
            _leaf("step_go"),
        )
    )

    graph = _applied(root, _plan(before, after, _graph_of(root)))

    assert graph.steps["step_orth"].search_name == "GenesByOrthologs"
    assert _shape(graph) == "(step_orth[step_text] INTERSECT step_go)"


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
