"""Edge-case tests for strategy AST invariants.

Tests for the OLD imperative tools (create_leaf_step, combine_steps, etc.)
were deleted with those tools in SC-D22. The structural invariants that
made them necessary are now enforced at the AST construction layer —
exercised here.
"""

import pytest
from pydantic import ValidationError

from pathfinder.domain.strategy.ast import StrategyStepNode
from pathfinder.domain.strategy.ops import CombineOp


def test_combine_step_with_same_input_twice_rejected_at_ast_layer() -> None:
    """A combine that uses the same step on both inputs is structurally
    invalid (WDK rejects on push, and ``X ∩ X = X`` is a no-op anyway).
    The AST validator refuses to construct it, so no code path can
    produce a malformed combine."""
    leaf = StrategyStepNode(search_name="GenesByTaxon", display_name="Step A")
    with pytest.raises(ValidationError, match="same step on both inputs"):
        StrategyStepNode(
            search_name="__combine__",
            display_name="Self-union",
            primary_input=leaf,
            secondary_input=leaf,
            operator=CombineOp.UNION,
        )


def test_combine_requires_operator() -> None:
    leaf_a = StrategyStepNode(search_name="GenesByTaxon")
    leaf_b = StrategyStepNode(search_name="GenesByText")
    with pytest.raises(ValidationError, match="operator is required"):
        StrategyStepNode(
            search_name="__combine__",
            primary_input=leaf_a,
            secondary_input=leaf_b,
        )


def test_secondary_input_requires_primary() -> None:
    leaf = StrategyStepNode(search_name="GenesByTaxon")
    with pytest.raises(ValidationError, match="secondaryInput requires primaryInput"):
        StrategyStepNode(
            search_name="__combine__",
            secondary_input=leaf,
            operator=CombineOp.UNION,
        )


def test_colocate_requires_colocation_params() -> None:
    leaf_a = StrategyStepNode(search_name="GenesByTaxon")
    leaf_b = StrategyStepNode(search_name="GenesByText")
    with pytest.raises(ValidationError, match="colocationParams is required"):
        StrategyStepNode(
            search_name="__combine__",
            primary_input=leaf_a,
            secondary_input=leaf_b,
            operator=CombineOp.COLOCATE,
        )
