"""What a step is made of, and what a write to one may change.

A step's kind is the number of answer parameters its search declares. The
boolean operand names embed the record class full name, which is not the name
a step reports.
"""

from __future__ import annotations

from typing import Any

import pytest

from pathfinder.devtools.wdk_fixtures import load_recorded
from pathfinder.domain.strategy.ops import BOOLEAN_OPERATORS, CombineOp, parse_op
from pathfinder.integrations.veupathdb.client import VEuPathDBClient
from pathfinder.integrations.veupathdb.strategy_api import StrategyAPI
from pathfinder.integrations.veupathdb.wdk_models import (
    WDKFilterValue,
    WDKSearch,
    WDKSearchResponse,
    WDKStepTree,
)


def _search(name: str) -> WDKSearch:
    return WDKSearchResponse.model_validate(load_recorded(name).json_body()).search_data


def _input_step_names(search: WDKSearch) -> list[str]:
    return [p.name for p in search.parameters or [] if p.type == "input-step"]


class TestWdkStep001KindIsTheAnswerParameterCount:
    def test_wdk_step_001_a_leaf_declares_no_answer_parameter(self) -> None:
        assert _input_step_names(_search("search_genes_by_molecular_weight")) == []

    def test_wdk_step_001_a_transform_declares_one(self) -> None:
        assert _input_step_names(_search("search_genes_by_orthologs")) == [
            "gene_result"
        ]

    def test_wdk_step_001_a_combined_step_declares_two(self) -> None:
        names = _input_step_names(_search("search_boolean_transcript"))

        assert len(names) == 2

    def test_wdk_step_001_an_input_parameter_has_no_naming_convention(self) -> None:
        # `bq_left_op_*` is specific to the generated boolean query.
        transform = _search("search_genes_by_orthologs")

        assert _input_step_names(transform) == ["gene_result"]
        assert not any(n.startswith("bq_") for n in _input_step_names(transform))

    def test_wdk_step_001_the_order_of_declaration_is_the_slot_order(self) -> None:
        # Ordinal 0 is the primary input, ordinal 1 the secondary.
        left, right = _input_step_names(_search("search_boolean_transcript"))

        assert left.startswith("bq_left_op_")
        assert right.startswith("bq_right_op_")


class TestWdkStep006OperandNamesEmbedTheFullName:
    def test_wdk_step_006_the_operand_names_carry_the_record_class_full_name(
        self,
    ) -> None:
        search = _search("search_boolean_transcript")

        assert search.param_names == [
            "bq_left_op_TranscriptRecordClasses_TranscriptRecordClass",
            "bq_right_op_TranscriptRecordClasses_TranscriptRecordClass",
            "bq_operator",
        ]

    def test_wdk_step_006_the_operator_name_is_a_bare_constant(self) -> None:
        search = _search("search_boolean_transcript")

        assert "bq_operator" in search.param_names

    def test_wdk_step_006_the_step_reports_the_url_segment_instead(self) -> None:
        # There is no string transformation from one to the other.
        search = _search("search_boolean_transcript")

        assert search.output_record_class_name == "transcript"
        assert "transcript" not in search.param_names[0].removeprefix("bq_left_op_")

    async def test_wdk_step_006_the_names_are_read_from_the_search(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client = VEuPathDBClient("https://example.invalid/service")
        api = StrategyAPI(client)

        recorded = WDKSearchResponse.model_validate(
            load_recorded("search_boolean_transcript").json_body()
        )

        async def details(record_type: str, search_name: str, **_: object) -> Any:
            del record_type, search_name
            return recorded

        async def searches(record_type: str) -> list[WDKSearch]:
            del record_type
            return [recorded.search_data]

        monkeypatch.setattr(client, "get_search_details", details)
        monkeypatch.setattr(client, "get_searches", searches)

        left, right, operator = await api._get_boolean_param_names("transcript")

        assert left == "bq_left_op_TranscriptRecordClasses_TranscriptRecordClass"
        assert right == "bq_right_op_TranscriptRecordClasses_TranscriptRecordClass"
        assert operator == "bq_operator"


class TestWdkStep008BothOperandsAreOneRecordClass:
    def test_wdk_step_008_the_allowed_inputs_are_the_same_single_class(self) -> None:
        search = _search("search_boolean_transcript")

        assert search.allowed_primary_input_record_class_names == ["transcript"]
        assert search.allowed_secondary_input_record_class_names == ["transcript"]

    def test_wdk_step_008_the_result_is_that_same_class(self) -> None:
        assert _search("search_boolean_transcript").output_record_class_name == (
            "transcript"
        )

    def test_wdk_step_008_colocation_is_not_a_boolean_operator(self) -> None:
        # Colocation relates different kinds of thing, so it is excluded.
        assert CombineOp.COLOCATE not in BOOLEAN_OPERATORS
        assert CombineOp.INTERSECT in BOOLEAN_OPERATORS

    def test_wdk_step_008_the_operator_terms_are_the_vocabulary_terms(self) -> None:
        # Send MINUS, not LEFT_MINUS: display and term differ on four of six.
        assert parse_op("LEFT_MINUS") is CombineOp.MINUS
        assert CombineOp.MINUS.value == "MINUS"


class TestWdkStep003ASearchConfigWriteCannotRewire:
    async def test_wdk_step_003_an_answer_parameter_survives_a_filter_write(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Dropping an answer parameter is changing it, which is a 422.
        step: dict[str, Any] = {
            "id": 9,
            "searchName": "GenesByOrthologs",
            "recordClassName": "transcript",
            "validation": {"level": "SEMANTIC", "isValid": True},
            "searchConfig": {
                "parameters": {"gene_result": "440085983", "organism": "[]"},
                "wdkWeight": 0,
            },
        }
        bodies: list[dict[str, Any]] = []

        async def read(path: str, **_: object) -> Any:
            del path
            return step

        async def write(
            path: str, json: dict[str, Any] | None = None, **_: object
        ) -> Any:
            del path
            bodies.append(json or {})
            return None

        client = VEuPathDBClient("https://example.invalid/service")
        monkeypatch.setattr(client, "get", read)
        monkeypatch.setattr(client, "put", write)

        await client.update_step_filters(
            "1", 9, [WDKFilterValue(name="f", value=None, disabled=False)]
        )

        assert bodies[-1]["parameters"]["gene_result"] == "440085983"


class TestWdkStrat001ANodeCarriesAStepIdAndNothingElse:
    def test_wdk_strat_001_a_leaf_node_serializes_to_one_key(self) -> None:
        node = WDKStepTree(stepId=7)

        assert node.model_dump(by_alias=True, exclude_none=True) == {"stepId": 7}

    def test_wdk_strat_001_a_combined_node_carries_its_two_inputs(self) -> None:
        node = WDKStepTree(
            stepId=3,
            primaryInput=WDKStepTree(stepId=1),
            secondaryInput=WDKStepTree(stepId=2),
        )

        assert node.model_dump(by_alias=True, exclude_none=True) == {
            "stepId": 3,
            "primaryInput": {"stepId": 1},
            "secondaryInput": {"stepId": 2},
        }

    def test_wdk_strat_001_no_step_data_rides_on_the_tree(self) -> None:
        # The tempting shape is a tree of whole steps; every read then has two
        # copies of a step's data.
        keys = set(WDKStepTree.model_fields)

        assert keys == {"step_id", "primary_input", "secondary_input"}
