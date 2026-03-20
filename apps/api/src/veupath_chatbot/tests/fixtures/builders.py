"""Shared builder helpers for test data construction.

Consolidates factory functions that were duplicated across 3+ test files.
Import from here instead of redefining in each test module.
"""

from dataclasses import dataclass

from veupath_chatbot.domain.parameters.specs import ParamSpecNormalized
from veupath_chatbot.domain.strategy.ast import PlanStepNode
from veupath_chatbot.domain.strategy.ops import CombineOp


@dataclass
class ParamSpecConfig:
    """Configuration for :func:`make_param_spec`."""

    name: str = "test_param"
    param_type: str = "string"
    allow_empty: bool = False
    min_selected: int | None = None
    max_selected: int | None = None
    vocabulary: dict | list | None = None
    count_only_leaves: bool = False
    is_number: bool = False
    min_value: float | None = None
    max_value: float | None = None
    increment: float | None = None
    max_length: int | None = None


# ---------------------------------------------------------------------------
# PlanStepNode builders -- used in test_graph_integrity, test_graph_ops,
# test_strategy_session
# ---------------------------------------------------------------------------


def make_leaf(
    step_id: str,
    name: str = "GenesByTextSearch",
    display: str | None = None,
    parameters: dict | None = None,
) -> PlanStepNode:
    """Create a leaf (search) PlanStepNode."""
    return PlanStepNode(
        search_name=name,
        parameters=parameters if parameters is not None else {},
        display_name=display,
        id=step_id,
    )


def make_combine(
    step_id: str,
    left: PlanStepNode,
    right: PlanStepNode,
    operator: CombineOp = CombineOp.INTERSECT,
) -> PlanStepNode:
    """Create a combine (boolean) PlanStepNode."""
    return PlanStepNode(
        search_name="BooleanQuestion",
        parameters={},
        primary_input=left,
        secondary_input=right,
        operator=operator,
        id=step_id,
    )


def make_transform(
    step_id: str,
    input_step: PlanStepNode,
    name: str = "GenesByOrthologs",
    parameters: dict | None = None,
) -> PlanStepNode:
    """Create a transform (unary) PlanStepNode."""
    return PlanStepNode(
        search_name=name,
        parameters=parameters if parameters is not None else {"organism": "Pf3D7"},
        primary_input=input_step,
        id=step_id,
    )


# ---------------------------------------------------------------------------
# ParamSpecNormalized builder -- used in test_normalizer, test_value_helpers,
# test_canonicalize
# ---------------------------------------------------------------------------


def make_param_spec(cfg: ParamSpecConfig | None = None) -> ParamSpecNormalized:
    """Create a ParamSpecNormalized for parameter validation tests."""
    c = cfg or ParamSpecConfig()
    return ParamSpecNormalized(
        name=c.name,
        param_type=c.param_type,
        allow_empty_value=c.allow_empty,
        min_selected_count=c.min_selected,
        max_selected_count=c.max_selected,
        vocabulary=c.vocabulary,
        count_only_leaves=c.count_only_leaves,
        is_number=c.is_number,
        min_value=c.min_value,
        max_value=c.max_value,
        increment=c.increment,
        max_length=c.max_length,
    )
