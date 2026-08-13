"""Tests that parameter canonicalization validates and normalizes a strategy before
it reaches WDK."""

from collections.abc import Mapping

import pytest
from pydantic import JsonValue

from pathfinder.domain.parameters.values import (
    MultiPickValue,
    NumberValue,
    StringValue,
)
from pathfinder.domain.strategy.ast import StrategyStepNode
from pathfinder.domain.strategy.strategy_ast import StrategyAst
from pathfinder.domain.strategy.validation import StepValidation
from pathfinder.integrations.veupathdb.wdk_models import (
    WDKSearch,
    WDKSearchResponse,
)
from pathfinder.integrations.veupathdb.wdk_parameters import (
    WDKEnumParam,
    WDKNumberParam,
    WDKParameter,
    WDKStringParam,
)
from pathfinder.platform.errors import ValidationError
from pathfinder.services.strategies.plan_normalize import (
    canonicalize_strategy_ast_parameters,
)


def _make_tree_vocab() -> dict[str, object]:
    """A tree vocabulary with one parent term and two leaf terms."""
    return {
        "data": {"term": "Plasmodium", "display": "Plasmodium"},
        "children": [
            {
                "data": {"term": "Pf3D7", "display": "P. falciparum 3D7"},
                "children": [],
            },
            {
                "data": {"term": "PvP01", "display": "P. vivax P01"},
                "children": [],
            },
        ],
    }


def _make_search_response(
    search_name: str,
    params: list[WDKParameter],
) -> WDKSearchResponse:
    """Builds a minimal search response."""
    return WDKSearchResponse(
        search_data=WDKSearch(
            url_segment=search_name,
            display_name=search_name,
            parameters=params,
            param_names=[p.name for p in params],
        ),
        validation=StepValidation(),
    )


async def _noop_loader(
    _record_type: str,
    _name: str,
    _params: Mapping[str, JsonValue],
) -> WDKSearchResponse:
    """A default loader. Each test supplies its own."""
    msg = "Should not be called"
    raise AssertionError(msg)


async def test_canonicalize_expands_parent_to_leaves():
    """A parent term on a leaf-only param expands to its leaf descendants."""
    vocab = _make_tree_vocab()
    plan = StrategyAst(
        record_type="transcript",
        root=StrategyStepNode(
            search_name="GenesByTaxon",
            parameters={"organism": MultiPickValue(values=["Plasmodium"])},
            id="step_1",
        ),
    )

    async def load_details(
        _rt: str, _name: str, _params: Mapping[str, JsonValue]
    ) -> WDKSearchResponse:
        return _make_search_response(
            "GenesByTaxon",
            [
                WDKEnumParam(
                    name="organism",
                    type="multi-pick-vocabulary",
                    vocabulary=vocab,
                    count_only_leaves=True,
                    min_selected_count=1,
                ),
            ],
        )

    result = await canonicalize_strategy_ast_parameters(
        strategy_ast=plan,
        site_id="plasmodb",
        load_search_details=load_details,
    )

    assert result.root.parameters["organism"] == MultiPickValue(
        values=["Pf3D7", "PvP01"]
    )


async def test_canonicalize_validates_unknown_param():
    """An unknown parameter raises a validation error instead of passing through."""
    plan = StrategyAst(
        record_type="transcript",
        root=StrategyStepNode(
            search_name="GenesByTaxon",
            parameters={"bogus_param": StringValue(value="value")},
            id="step_1",
        ),
    )

    async def load_details(
        _rt: str, _name: str, _params: Mapping[str, JsonValue]
    ) -> WDKSearchResponse:
        return _make_search_response(
            "GenesByTaxon",
            [
                WDKEnumParam(
                    name="organism",
                    type="multi-pick-vocabulary",
                    vocabulary=_make_tree_vocab(),
                    count_only_leaves=True,
                ),
            ],
        )

    with pytest.raises(ValidationError, match="Unknown parameter"):
        await canonicalize_strategy_ast_parameters(
            strategy_ast=plan,
            site_id="plasmodb",
            load_search_details=load_details,
        )


async def test_canonicalize_leaves_combine_nodes_untouched():
    """A combine node has no WDK params, so canonicalization skips it."""
    plan = StrategyAst(
        record_type="transcript",
        root=StrategyStepNode(
            search_name="BooleanQuestion",
            parameters={"bq_operator": StringValue(value="INTERSECT")},
            operator="INTERSECT",
            primary_input=StrategyStepNode(
                search_name="GenesByTaxon",
                parameters={"organism": MultiPickValue(values=["Pf3D7"])},
                id="step_1",
            ),
            secondary_input=StrategyStepNode(
                search_name="GenesByTextSearch",
                parameters={"text_expression": StringValue(value="kinase")},
                id="step_2",
            ),
            id="step_combine",
        ),
    )

    async def load_details(
        _rt: str, name: str, _params: Mapping[str, JsonValue]
    ) -> WDKSearchResponse:
        if name == "GenesByTaxon":
            return _make_search_response(
                "GenesByTaxon",
                [
                    WDKEnumParam(
                        name="organism",
                        type="multi-pick-vocabulary",
                        vocabulary=_make_tree_vocab(),
                        count_only_leaves=True,
                        min_selected_count=1,
                    ),
                ],
            )
        return _make_search_response(
            "GenesByTextSearch",
            [
                WDKStringParam(
                    name="text_expression",
                    type="string",
                ),
            ],
        )

    result = await canonicalize_strategy_ast_parameters(
        strategy_ast=plan,
        site_id="plasmodb",
        load_search_details=load_details,
    )

    # The combine node keeps no boolean-question keys.
    assert "bq_operator" not in result.root.parameters

    # The child nodes are still canonicalized.
    assert result.root.primary_input is not None
    assert result.root.primary_input.parameters["organism"] == MultiPickValue(
        values=["Pf3D7"]
    )
    assert result.root.secondary_input is not None
    assert result.root.secondary_input.parameters["text_expression"] == StringValue(
        value="kinase"
    )


async def test_canonicalize_numeric_range_validation():
    """A numeric value above the maximum raises a validation error."""
    plan = StrategyAst(
        record_type="transcript",
        root=StrategyStepNode(
            search_name="GenesByExpression",
            parameters={"fold_change": NumberValue(value=999)},
            id="step_1",
        ),
    )

    async def load_details(
        _rt: str, _name: str, _params: Mapping[str, JsonValue]
    ) -> WDKSearchResponse:
        return _make_search_response(
            "GenesByExpression",
            [
                WDKNumberParam(
                    name="fold_change",
                    type="number",
                    min=0.0,
                    max=100.0,
                ),
            ],
        )

    with pytest.raises(ValidationError, match="exceeds maximum"):
        await canonicalize_strategy_ast_parameters(
            strategy_ast=plan,
            site_id="plasmodb",
            load_search_details=load_details,
        )
