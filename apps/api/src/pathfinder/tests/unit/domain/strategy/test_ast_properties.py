"""Property tests for the strategy AST.

Hypothesis generates valid trees and exercises the structural invariants of
``StrategyStepNode`` and ``StrategyAst``: walk order, kind inference,
JSON round-trip, and the validators that guard combine / colocate / id
uniqueness rules. Negative cases pin the rejection paths so silent loosening
of the validators fails loudly.
"""

from __future__ import annotations

import string

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from pathfinder.domain.parameters.values import (
    MultiPickValue,
    NumberValue,
    StringValue,
)
from pathfinder.domain.strategy.ast import (
    COMBINE_SEARCH_NAME,
    StrategyStepNode,
    walk_step_tree,
)
from pathfinder.domain.strategy.ops import ColocationParams, CombineOp
from pathfinder.domain.strategy.strategy_ast import StrategyAst

# --- Hypothesis building blocks -------------------------------------------------

_search_names = st.text(
    alphabet=string.ascii_lowercase + "_",
    min_size=1,
    max_size=20,
).filter(lambda s: s != COMBINE_SEARCH_NAME)

_param_values = st.one_of(
    st.builds(StringValue, value=st.text(min_size=1, max_size=10)),
    st.builds(NumberValue, value=st.floats(min_value=-1000, max_value=1000)),
    st.builds(
        MultiPickValue,
        values=st.lists(st.text(min_size=1, max_size=8), min_size=1, max_size=3),
    ),
)

_param_dicts = st.dictionaries(
    keys=st.text(alphabet=string.ascii_lowercase, min_size=1, max_size=8),
    values=_param_values,
    max_size=3,
)

_boolean_ops = st.sampled_from(
    [
        CombineOp.INTERSECT,
        CombineOp.UNION,
        CombineOp.MINUS,
        CombineOp.RMINUS,
        CombineOp.LONLY,
        CombineOp.RONLY,
    ],
)

_colocation = st.builds(
    ColocationParams,
    operation=st.sampled_from(["overlaps", "contains", "is contained in"]),
    strand=st.sampled_from(["either strand", "same strand", "opposite strand"]),
    output=st.sampled_from(["a", "b"]),
    begin_offset_a=st.integers(min_value=0, max_value=10_000),
    end_offset_a=st.integers(min_value=0, max_value=10_000),
    begin_offset_b=st.integers(min_value=0, max_value=10_000),
    end_offset_b=st.integers(min_value=0, max_value=10_000),
)

_search_node = st.builds(
    StrategyStepNode,
    search_name=_search_names,
    parameters=_param_dicts,
)


def _transform_factory(child: StrategyStepNode, sn: str, pd: dict) -> StrategyStepNode:
    return StrategyStepNode(search_name=sn, parameters=pd, primary_input=child)


def _combine_factory(
    left: StrategyStepNode, right: StrategyStepNode, op: CombineOp,
) -> StrategyStepNode | None:
    if left.id == right.id:
        return None
    return StrategyStepNode(
        search_name=COMBINE_SEARCH_NAME,
        primary_input=left,
        secondary_input=right,
        operator=op,
    )


def _colocate_factory(
    left: StrategyStepNode, right: StrategyStepNode, col: ColocationParams,
) -> StrategyStepNode | None:
    if left.id == right.id:
        return None
    return StrategyStepNode(
        search_name=COMBINE_SEARCH_NAME,
        primary_input=left,
        secondary_input=right,
        operator=CombineOp.COLOCATE,
        colocation_params=col,
    )


def _extend(children: st.SearchStrategy[StrategyStepNode]) -> st.SearchStrategy[StrategyStepNode]:
    return st.one_of(
        st.builds(_transform_factory, children, _search_names, _param_dicts),
        st.builds(_combine_factory, children, children, _boolean_ops).filter(
            lambda n: n is not None,
        ),
        st.builds(_colocate_factory, children, children, _colocation).filter(
            lambda n: n is not None,
        ),
    )


_trees = st.recursive(_search_node, _extend, max_leaves=8)

_PROFILE = settings(
    max_examples=120,
    suppress_health_check=[HealthCheck.too_slow],
    deadline=None,
)


# --- Helpers --------------------------------------------------------------------


def _count_nodes(n: StrategyStepNode) -> int:
    total = 1
    if n.primary_input is not None:
        total += _count_nodes(n.primary_input)
    if n.secondary_input is not None:
        total += _count_nodes(n.secondary_input)
    return total


# --- Property tests -------------------------------------------------------------


@_PROFILE
@given(_trees)
def test_walk_step_tree_is_post_order_and_unique(root: StrategyStepNode) -> None:
    steps = walk_step_tree(root)
    ids = [s.id for s in steps]
    assert len(ids) == len(set(ids)), (
        f"walk_step_tree returned duplicate ids: {ids}"
    )
    assert steps[-1] is root, "root must be visited last in post-order traversal"
    assert len(steps) == _count_nodes(root)
    seen: set[str] = set()
    for node in steps:
        if node.primary_input is not None:
            assert node.primary_input.id in seen, (
                "primary_input must be visited before parent"
            )
        if node.secondary_input is not None:
            assert node.secondary_input.id in seen, (
                "secondary_input must be visited before parent"
            )
        seen.add(node.id)


@_PROFILE
@given(_trees)
def test_infer_kind_matches_structure(root: StrategyStepNode) -> None:
    for node in walk_step_tree(root):
        kind = node.infer_kind()
        if node.primary_input is not None and node.secondary_input is not None:
            assert kind == "combine"
        elif node.primary_input is not None:
            assert kind == "transform"
        else:
            assert kind == "search"


@_PROFILE
@given(_trees)
def test_strategy_ast_json_round_trip_is_identity(root: StrategyStepNode) -> None:
    original = StrategyAst(record_type="transcript", root=root)
    raw = original.model_dump_json(by_alias=True)
    restored = StrategyAst.model_validate_json(raw)
    assert original == restored
    assert original.model_dump(by_alias=True) == restored.model_dump(by_alias=True)


@_PROFILE
@given(_trees)
def test_strategy_ast_python_round_trip_is_identity(root: StrategyStepNode) -> None:
    original = StrategyAst(record_type="transcript", root=root)
    payload = original.model_dump(by_alias=True)
    restored = StrategyAst.model_validate(payload)
    assert original == restored


@_PROFILE
@given(_trees)
def test_combine_nodes_carry_combine_search_name(root: StrategyStepNode) -> None:
    for node in walk_step_tree(root):
        if node.primary_input is not None and node.secondary_input is not None:
            assert node.search_name == COMBINE_SEARCH_NAME


# --- Negative tests pin the validators ------------------------------------------


def test_secondary_without_primary_is_rejected() -> None:
    leaf = StrategyStepNode(search_name="a")
    with pytest.raises(ValidationError, match="secondaryInput requires primaryInput"):
        StrategyStepNode(
            search_name=COMBINE_SEARCH_NAME,
            secondary_input=leaf,
            operator=CombineOp.INTERSECT,
        )


def test_combine_without_operator_is_rejected() -> None:
    a = StrategyStepNode(search_name="a")
    b = StrategyStepNode(search_name="b")
    with pytest.raises(ValidationError, match="operator is required"):
        StrategyStepNode(
            search_name=COMBINE_SEARCH_NAME,
            primary_input=a,
            secondary_input=b,
        )


def test_combine_with_same_step_id_is_rejected() -> None:
    a = StrategyStepNode(search_name="a", id="step_dup")
    b = StrategyStepNode(search_name="b", id="step_dup")
    with pytest.raises(ValidationError, match="cannot use the same step on both inputs"):
        StrategyStepNode(
            search_name=COMBINE_SEARCH_NAME,
            primary_input=a,
            secondary_input=b,
            operator=CombineOp.INTERSECT,
        )


def test_colocate_without_colocation_params_is_rejected() -> None:
    a = StrategyStepNode(search_name="a")
    b = StrategyStepNode(search_name="b")
    with pytest.raises(ValidationError, match="colocationParams is required"):
        StrategyStepNode(
            search_name=COMBINE_SEARCH_NAME,
            primary_input=a,
            secondary_input=b,
            operator=CombineOp.COLOCATE,
        )


def test_colocation_params_without_colocate_is_rejected() -> None:
    a = StrategyStepNode(search_name="a")
    b = StrategyStepNode(search_name="b")
    with pytest.raises(ValidationError, match="colocationParams is only allowed"):
        StrategyStepNode(
            search_name=COMBINE_SEARCH_NAME,
            primary_input=a,
            secondary_input=b,
            operator=CombineOp.UNION,
            colocation_params=ColocationParams(),
        )


def test_expanded_strategy_id_outside_combine_is_rejected() -> None:
    with pytest.raises(ValidationError, match="expandedStrategyId is only valid on combine"):
        StrategyStepNode(
            search_name="a",
            expanded_strategy_id=42,
            expanded_name="saved-1",
        )


def test_expanded_strategy_id_without_name_is_rejected() -> None:
    a = StrategyStepNode(search_name="a")
    b = StrategyStepNode(search_name="b")
    with pytest.raises(ValidationError, match="expandedName is required"):
        StrategyStepNode(
            search_name=COMBINE_SEARCH_NAME,
            primary_input=a,
            secondary_input=b,
            operator=CombineOp.INTERSECT,
            expanded_strategy_id=42,
        )


def test_combine_default_search_name_is_injected() -> None:
    a = StrategyStepNode(search_name="a")
    b = StrategyStepNode(search_name="b")
    node = StrategyStepNode(
        primary_input=a,
        secondary_input=b,
        operator=CombineOp.INTERSECT,
    )
    assert node.search_name == COMBINE_SEARCH_NAME


def test_strategy_ast_rejects_duplicate_ids_across_tree() -> None:
    leaf_x = StrategyStepNode(search_name="a", id="dup")
    leaf_y = StrategyStepNode(search_name="b", id="dup")
    leaf_other = StrategyStepNode(search_name="c")
    root = StrategyStepNode(
        search_name=COMBINE_SEARCH_NAME,
        primary_input=leaf_x,
        secondary_input=StrategyStepNode(
            search_name=COMBINE_SEARCH_NAME,
            primary_input=leaf_y,
            secondary_input=leaf_other,
            operator=CombineOp.INTERSECT,
        ),
        operator=CombineOp.UNION,
    )
    with pytest.raises(ValidationError, match="duplicate step ids"):
        StrategyAst(record_type="transcript", root=root)
