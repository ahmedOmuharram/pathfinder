"""The exact JSON a strategy is persisted and served as.

Every stored conversation and every OpenAPI response carries this shape, so a
key that moves here is a migration. The fixture holds one node of each kind, a
detached root, and a combine imported from WDK under its real question name.
"""

from __future__ import annotations

from assistant_core.platform.types import JSONObject

from pathfinder.domain.parameters.values import MultiPickValue, StringValue
from pathfinder.domain.strategy.ast import COMBINE_SEARCH_NAME, StrategyStepNode
from pathfinder.domain.strategy.graph_model import flatten_tree, rebuild_tree
from pathfinder.domain.strategy.ops import CombineOp
from pathfinder.domain.strategy.strategy_ast import StrategyAst

_BOOLEAN_QUESTION = "boolean_question_TranscriptRecordClasses_TranscriptRecordClass"


def _fixture() -> StrategyAst:
    return StrategyAst(
        record_type="transcript",
        name="kinases",
        root=StrategyStepNode(
            id="c",
            search_name=COMBINE_SEARCH_NAME,
            operator=CombineOp.INTERSECT,
            primary_input=StrategyStepNode(
                id="t",
                search_name="GenesByOrthologs",
                primary_input=StrategyStepNode(
                    id="a",
                    search_name="GenesByText",
                    parameters={"text_expression": StringValue(value="kinase")},
                ),
            ),
            secondary_input=StrategyStepNode(
                id="imported",
                search_name=_BOOLEAN_QUESTION,
                operator=CombineOp.UNION,
                primary_input=StrategyStepNode(id="b", search_name="GenesByTaxon"),
                secondary_input=StrategyStepNode(
                    id="d",
                    search_name="GenesByGoTerm",
                    parameters={"go_term": MultiPickValue(values=["GO:0004672"])},
                ),
            ),
        ),
        detached_roots=[StrategyStepNode(id="z", search_name="GenesBySignalPeptide")],
    )


_LEAF_DEFAULTS: JSONObject = {
    "parameters": {},
    "filters": [],
    "analyses": [],
    "reports": [],
}

_EXPECTED: JSONObject = {
    "recordType": "transcript",
    "name": "kinases",
    "root": {
        "id": "c",
        "searchName": "__combine__",
        "operator": "INTERSECT",
        **_LEAF_DEFAULTS,
        "primaryInput": {
            "id": "t",
            "searchName": "GenesByOrthologs",
            **_LEAF_DEFAULTS,
            "primaryInput": {
                "id": "a",
                "searchName": "GenesByText",
                **_LEAF_DEFAULTS,
                "parameters": {
                    "text_expression": {"type": "string", "value": "kinase"}
                },
            },
        },
        "secondaryInput": {
            "id": "imported",
            "searchName": _BOOLEAN_QUESTION,
            "operator": "UNION",
            **_LEAF_DEFAULTS,
            "primaryInput": {
                "id": "b",
                "searchName": "GenesByTaxon",
                **_LEAF_DEFAULTS,
            },
            "secondaryInput": {
                "id": "d",
                "searchName": "GenesByGoTerm",
                **_LEAF_DEFAULTS,
                "parameters": {
                    "go_term": {
                        "type": "multi-pick-vocabulary",
                        "values": ["GO:0004672"],
                    }
                },
            },
        },
    },
    "detachedRoots": [
        {"id": "z", "searchName": "GenesBySignalPeptide", **_LEAF_DEFAULTS},
    ],
}


def _dump(ast: StrategyAst) -> JSONObject:
    return ast.model_dump(by_alias=True, exclude_none=True, mode="json")


class TestThePersistedShape:
    def test_the_fixture_serializes_to_the_pinned_json(self) -> None:
        assert _dump(_fixture()) == _EXPECTED

    def test_the_json_parses_back_to_the_same_model(self) -> None:
        ast = _fixture()

        assert StrategyAst.model_validate(ast.model_dump(by_alias=True)) == ast

    def test_the_flat_split_and_rejoin_is_the_identity(self) -> None:
        root = _fixture().root

        assert rebuild_tree(root.id, flatten_tree(root)) == root

    def test_an_imported_combine_keeps_its_wdk_question_name(self) -> None:
        """A combine WDK named is not the sentinel, and the name survives."""
        steps = flatten_tree(_fixture().root)

        assert steps["imported"].search_name == _BOOLEAN_QUESTION
        assert steps["c"].search_name is None
        assert rebuild_tree("c", steps).search_name == COMBINE_SEARCH_NAME
