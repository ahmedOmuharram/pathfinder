"""Which nodes canonicalization visits, and which it skips.

A node with two inputs and a node carrying the combine sentinel both skip the
WDK spec load; every other node is canonicalized once.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import JsonValue

from pathfinder.domain.parameters.values import MultiPickValue, ParamValue, StringValue
from pathfinder.domain.strategy.ast import COMBINE_SEARCH_NAME, StrategyStepNode
from pathfinder.domain.strategy.ops import CombineOp
from pathfinder.domain.strategy.strategy_ast import StrategyAst
from pathfinder.domain.strategy.validation import StepValidation
from pathfinder.integrations.veupathdb.wdk_models import WDKSearch, WDKSearchResponse
from pathfinder.integrations.veupathdb.wdk_parameters import (
    WDKParameter,
    WDKStringParam,
)
from pathfinder.services.strategies.plan_normalize import (
    canonicalize_strategy_ast_parameters,
)


class _RecordingLoader:
    """Answers every search with one string parameter and records the names."""

    def __init__(self) -> None:
        self.names: list[str] = []

    async def __call__(
        self, record_type: str, name: str, params: Mapping[str, JsonValue]
    ) -> WDKSearchResponse:
        del record_type, params
        self.names.append(name)
        parameters: list[WDKParameter] = [
            WDKStringParam(name="text_expression", type="string")
        ]
        return WDKSearchResponse(
            search_data=WDKSearch(
                url_segment=name,
                display_name=name,
                parameters=parameters,
                param_names=[p.name for p in parameters],
            ),
            validation=StepValidation(level="NONE", is_valid=False),
        )


def _bq_params() -> dict[str, ParamValue]:
    return {
        "bq_operator": StringValue(value="INTERSECT"),
        "bq_left_op_TranscriptRecordClasses_TranscriptRecordClass": MultiPickValue(
            values=["1"]
        ),
    }


async def test_a_transform_is_canonicalized_like_a_leaf() -> None:
    loader = _RecordingLoader()
    ast = StrategyAst(
        record_type="transcript",
        root=StrategyStepNode(
            id="t",
            search_name="GenesByOrthologs",
            parameters={"text_expression": StringValue(value="kinase")},
            primary_input=StrategyStepNode(
                id="a",
                search_name="GenesByText",
                parameters={"text_expression": StringValue(value="protease")},
            ),
        ),
    )

    result = await canonicalize_strategy_ast_parameters(
        strategy_ast=ast, site_id="plasmodb", load_search_details=loader
    )

    assert sorted(loader.names) == ["GenesByOrthologs", "GenesByText"]
    assert result.root.parameters["text_expression"] == StringValue(value="kinase")
    assert result.root.primary_input is not None
    assert result.root.primary_input.parameters["text_expression"] == StringValue(
        value="protease"
    )


async def test_a_half_wired_combine_is_skipped_and_loses_its_boolean_keys() -> None:
    loader = _RecordingLoader()
    ast = StrategyAst(
        record_type="transcript",
        root=StrategyStepNode(
            id="c",
            search_name=COMBINE_SEARCH_NAME,
            parameters=_bq_params(),
            primary_input=StrategyStepNode(
                id="a",
                search_name="GenesByText",
                parameters={"text_expression": StringValue(value="kinase")},
            ),
        ),
    )

    result = await canonicalize_strategy_ast_parameters(
        strategy_ast=ast, site_id="plasmodb", load_search_details=loader
    )

    assert loader.names == ["GenesByText"]
    assert result.root.parameters == {}


async def test_a_wired_combine_is_skipped_even_with_a_real_search_name() -> None:
    loader = _RecordingLoader()
    ast = StrategyAst(
        record_type="transcript",
        root=StrategyStepNode(
            id="c",
            search_name="boolean_question_TranscriptRecordClasses_TranscriptRecordClass",
            operator=CombineOp.INTERSECT,
            parameters=_bq_params(),
            primary_input=StrategyStepNode(id="a", search_name="GenesByText"),
            secondary_input=StrategyStepNode(id="b", search_name="GenesByTaxon"),
        ),
    )

    result = await canonicalize_strategy_ast_parameters(
        strategy_ast=ast, site_id="plasmodb", load_search_details=loader
    )

    assert sorted(loader.names) == ["GenesByTaxon", "GenesByText"]
    assert result.root.parameters == {}
