"""Verify that canonicalize_plan_parameters works correctly for push flows.

The push endpoint must run canonicalize_plan_parameters() so that
user-edited parameters (from the graph editor) are validated and
normalized before reaching WDK.  Without canonicalization, parent-node
selections on countOnlyLeaves params silently return 0 results.
"""

from collections.abc import Mapping

import pytest

from pathfinder.domain.strategy.ast import PlanStepNode
from pathfinder.domain.strategy.plan_payload import StrategyPlanPayload
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
from pathfinder.platform.types import JSONValue
from pathfinder.services.strategies.plan_normalize import (
    canonicalize_plan_parameters,
)

# -- Fixtures ----------------------------------------------------------------


def _make_tree_vocab() -> dict[str, object]:
    """A 2-level tree vocabulary: Plasmodium -> {Pf3D7, PvP01}."""
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
    """Build a minimal WDKSearchResponse for testing."""
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
    _params: Mapping[str, JSONValue],
) -> WDKSearchResponse:
    """Placeholder — overridden per test."""
    msg = "Should not be called"
    raise AssertionError(msg)


# -- Tests -------------------------------------------------------------------


async def test_canonicalize_expands_parent_to_leaves():
    """Parent organism selection must be expanded to leaf descendants.

    This is the core bug: if a user selects "Plasmodium" (parent) in a
    countOnlyLeaves=true param, WDK silently returns 0 genes.
    canonicalize_plan_parameters must expand it to ["Pf3D7", "PvP01"].
    """
    vocab = _make_tree_vocab()
    plan = StrategyPlanPayload(
        record_type="transcript",
        root=PlanStepNode(
            search_name="GenesByTaxon",
            parameters={"organism": ["Plasmodium"]},
            id="step_1",
        ),
    )

    async def load_details(
        _rt: str, _name: str, _params: Mapping[str, JSONValue]
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

    result = await canonicalize_plan_parameters(
        plan=plan,
        site_id="plasmodb",
        load_search_details=load_details,
    )

    # Parent "Plasmodium" must be expanded to leaf nodes.
    # SerializedParams coerces list → JSON string for WDK compatibility.
    assert result.root.parameters["organism"] == '["Pf3D7", "PvP01"]'


async def test_canonicalize_validates_unknown_param():
    """Unknown parameters must raise ValidationError, not pass through."""
    plan = StrategyPlanPayload(
        record_type="transcript",
        root=PlanStepNode(
            search_name="GenesByTaxon",
            parameters={"bogus_param": "value"},
            id="step_1",
        ),
    )

    async def load_details(
        _rt: str, _name: str, _params: Mapping[str, JSONValue]
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
        await canonicalize_plan_parameters(
            plan=plan,
            site_id="plasmodb",
            load_search_details=load_details,
        )


async def test_canonicalize_leaves_combine_nodes_untouched():
    """Combine nodes should not be canonicalized (they have no WDK params)."""
    plan = StrategyPlanPayload(
        record_type="transcript",
        root=PlanStepNode(
            search_name="BooleanQuestion",
            parameters={"bq_operator": "INTERSECT"},
            operator="INTERSECT",
            primary_input=PlanStepNode(
                search_name="GenesByTaxon",
                parameters={"organism": ["Pf3D7"]},
                id="step_1",
            ),
            secondary_input=PlanStepNode(
                search_name="GenesByTextSearch",
                parameters={"text_expression": "kinase"},
                id="step_2",
            ),
            id="step_combine",
        ),
    )

    async def load_details(
        _rt: str, name: str, _params: Mapping[str, JSONValue]
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

    result = await canonicalize_plan_parameters(
        plan=plan,
        site_id="plasmodb",
        load_search_details=load_details,
    )

    # Combine node: bq_ keys stripped, not sent to WDK spec lookup
    assert "bq_operator" not in result.root.parameters

    # Children still canonicalized
    assert result.root.primary_input is not None
    assert result.root.primary_input.parameters["organism"] == '["Pf3D7"]'
    assert result.root.secondary_input is not None
    assert result.root.secondary_input.parameters["text_expression"] == "kinase"


async def test_canonicalize_numeric_range_validation():
    """Out-of-range numeric values must be caught."""
    plan = StrategyPlanPayload(
        record_type="transcript",
        root=PlanStepNode(
            search_name="GenesByExpression",
            parameters={"fold_change": "999"},
            id="step_1",
        ),
    )

    async def load_details(
        _rt: str, _name: str, _params: Mapping[str, JSONValue]
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
        await canonicalize_plan_parameters(
            plan=plan,
            site_id="plasmodb",
            load_search_details=load_details,
        )
