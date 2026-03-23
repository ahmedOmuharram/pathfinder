"""Tests for AST parsing functions (domain/strategy/ast.py).

Verifies StepFilter.from_list(), StepAnalysis.from_list(), StepReport.from_list(),
ColocationParams.from_json(), PlanStepNode.infer_kind(), StrategyAST round-trip.
"""

import pytest
from pydantic import ValidationError as PydanticValidationError

from veupath_chatbot.domain.strategy.ast import (
    PlanStepNode,
    StepAnalysis,
    StepFilter,
    StepReport,
    StrategyAST,
)
from veupath_chatbot.domain.strategy.ops import ColocationParams, CombineOp


class TestParseFilters:
    def test_valid_filters(self) -> None:
        raw = [
            {"name": "gene_type", "value": "protein_coding"},
            {"name": "organism", "value": "pfal", "disabled": True},
        ]
        filters = StepFilter.from_list(raw)
        assert len(filters) == 2
        assert filters[0].name == "gene_type"
        assert filters[0].value == "protein_coding"
        assert filters[0].disabled is False
        assert filters[1].disabled is True

    def test_skips_non_dict_entries(self) -> None:
        raw = ["bad", 42, None, {"name": "good", "value": "x"}]
        filters = StepFilter.from_list(raw)
        assert len(filters) == 1
        assert filters[0].name == "good"

    def test_skips_entries_without_name(self) -> None:
        raw = [{"value": "x"}, {"name": "", "value": "y"}]
        filters = StepFilter.from_list(raw)
        assert len(filters) == 0

    def test_non_list_input(self) -> None:
        assert StepFilter.from_list(None) == []
        assert StepFilter.from_list("bad") == []
        assert StepFilter.from_list(42) == []

    def test_empty_list(self) -> None:
        assert StepFilter.from_list([]) == []

    def test_value_can_be_any_type(self) -> None:
        """Filter value is JSONValue — any type is valid."""
        raw = [{"name": "f", "value": [1, 2, 3]}]
        filters = StepFilter.from_list(raw)
        assert filters[0].value == [1, 2, 3]



class TestParseAnalyses:
    def test_camel_case_key(self) -> None:
        raw = [{"analysisType": "go_enrichment", "parameters": {"ontology": "BP"}}]
        analyses = StepAnalysis.from_list(raw)
        assert len(analyses) == 1
        assert analyses[0].analysis_type == "go_enrichment"
        assert analyses[0].parameters == {"ontology": "BP"}

    def test_snake_case_key(self) -> None:
        """analysis_type is also accepted."""
        raw = [{"analysis_type": "pathway_enrichment"}]
        analyses = StepAnalysis.from_list(raw)
        assert len(analyses) == 1
        assert analyses[0].analysis_type == "pathway_enrichment"

    def test_custom_name_camel(self) -> None:
        raw = [{"analysisType": "go", "customName": "My Analysis"}]
        analyses = StepAnalysis.from_list(raw)
        assert analyses[0].custom_name == "My Analysis"

    def test_custom_name_snake(self) -> None:
        raw = [{"analysisType": "go", "custom_name": "My Analysis"}]
        analyses = StepAnalysis.from_list(raw)
        assert analyses[0].custom_name == "My Analysis"

    def test_skips_without_analysis_type(self) -> None:
        raw = [{"parameters": {}}]
        assert StepAnalysis.from_list(raw) == []

    def test_skips_empty_analysis_type(self) -> None:
        raw = [{"analysisType": ""}]
        assert StepAnalysis.from_list(raw) == []

    def test_non_dict_params_default_empty(self) -> None:
        raw = [{"analysisType": "go", "parameters": "bad"}]
        analyses = StepAnalysis.from_list(raw)
        assert analyses[0].parameters == {}

    def test_non_list_input(self) -> None:
        assert StepAnalysis.from_list(None) == []
        assert StepAnalysis.from_list("bad") == []

    def test_skips_non_dict_entries(self) -> None:
        raw = ["bad", {"analysisType": "go"}]
        analyses = StepAnalysis.from_list(raw)
        assert len(analyses) == 1



class TestParseReports:
    def test_valid_report(self) -> None:
        raw = [{"reportName": "standard", "config": {"attributes": ["gene_id"]}}]
        reports = StepReport.from_list(raw)
        assert len(reports) == 1
        assert reports[0].report_name == "standard"
        assert reports[0].config == {"attributes": ["gene_id"]}

    def test_snake_case_key(self) -> None:
        raw = [{"report_name": "tabular"}]
        reports = StepReport.from_list(raw)
        assert reports[0].report_name == "tabular"

    def test_missing_report_name_defaults_standard(self) -> None:
        raw = [{"config": {}}]
        reports = StepReport.from_list(raw)
        assert reports[0].report_name == "standard"

    def test_non_dict_config_defaults_empty(self) -> None:
        raw = [{"reportName": "standard", "config": "bad"}]
        reports = StepReport.from_list(raw)
        assert reports[0].config == {}

    def test_non_list_input(self) -> None:
        assert StepReport.from_list(None) == []

    def test_empty_list(self) -> None:
        assert StepReport.from_list([]) == []



class TestParseColocationParams:
    def test_valid_params(self) -> None:
        raw = {"upstream": 1000, "downstream": 500, "strand": "same"}
        result = ColocationParams.from_json(raw)
        assert result is not None
        assert result.upstream == 1000
        assert result.downstream == 500
        assert result.strand == "same"

    def test_defaults(self) -> None:
        result = ColocationParams.from_json({})
        assert result is not None
        assert result.upstream == 0
        assert result.downstream == 0
        assert result.strand == "both"

    def test_non_dict_returns_none(self) -> None:
        assert ColocationParams.from_json(None) is None
        assert ColocationParams.from_json("bad") is None
        assert ColocationParams.from_json(42) is None

    def test_invalid_strand_defaults_both(self) -> None:
        result = ColocationParams.from_json({"strand": "invalid"})
        assert result is not None
        assert result.strand == "both"

    def test_float_distances_truncated(self) -> None:
        result = ColocationParams.from_json({"upstream": 1000.9, "downstream": 500.1})
        assert result is not None
        assert result.upstream == 1000
        assert result.downstream == 500


# ── PlanStepNode.infer_kind ───────────────────────────────────────


class TestInferKind:
    def test_search(self) -> None:
        node = PlanStepNode(search_name="GenesByTaxon")
        assert node.infer_kind() == "search"

    def test_transform(self) -> None:
        child = PlanStepNode(search_name="GenesByTaxon")
        node = PlanStepNode(search_name="Transform", primary_input=child)
        assert node.infer_kind() == "transform"

    def test_combine(self) -> None:
        left = PlanStepNode(search_name="S1")
        right = PlanStepNode(search_name="S2")
        node = PlanStepNode(
            search_name="bq",
            primary_input=left,
            secondary_input=right,
            operator=CombineOp.INTERSECT,
        )
        assert node.infer_kind() == "combine"


# ── StrategyAST.get_all_steps ─────────────────────────────────────


class TestGetAllSteps:
    def test_single_step(self) -> None:
        root = PlanStepNode(search_name="S1", id="step1")
        ast = StrategyAST(record_type="transcript", root=root)
        steps = ast.get_all_steps()
        assert len(steps) == 1
        assert steps[0].id == "step1"

    def test_depth_first_order(self) -> None:
        """DFS: left children visited before right, parent last."""
        left = PlanStepNode(search_name="S1", id="left")
        right = PlanStepNode(search_name="S2", id="right")
        root = PlanStepNode(
            search_name="bq",
            id="root",
            primary_input=left,
            secondary_input=right,
            operator=CombineOp.INTERSECT,
        )
        ast = StrategyAST(record_type="transcript", root=root)
        ids = [s.id for s in ast.get_all_steps()]
        assert ids == ["left", "right", "root"]

    def test_nested_tree(self) -> None:
        """Three-level tree: left-left, left, right, root."""
        ll = PlanStepNode(search_name="S1", id="ll")
        left = PlanStepNode(search_name="T", id="left", primary_input=ll)
        right = PlanStepNode(search_name="S2", id="right")
        root = PlanStepNode(
            search_name="bq",
            id="root",
            primary_input=left,
            secondary_input=right,
            operator=CombineOp.UNION,
        )
        ast = StrategyAST(record_type="transcript", root=root)
        ids = [s.id for s in ast.get_all_steps()]
        assert ids == ["ll", "left", "right", "root"]


# ── StrategyAST.get_step_by_id ────────────────────────────────────


class TestGetStepById:
    def test_found(self) -> None:
        root = PlanStepNode(search_name="S1", id="my_step")
        ast = StrategyAST(record_type="transcript", root=root)
        assert ast.get_step_by_id("my_step") is root

    def test_not_found(self) -> None:
        root = PlanStepNode(search_name="S1", id="my_step")
        ast = StrategyAST(record_type="transcript", root=root)
        assert ast.get_step_by_id("nonexistent") is None


# ── model_validate round-trip ──────────────────────────────────────


class TestModelValidate:
    def test_single_step(self) -> None:
        data = {
            "recordType": "transcript",
            "root": {
                "searchName": "GenesByTaxon",
                "parameters": {"organism": "pfal"},
                "id": "step1",
            },
        }
        ast = StrategyAST.model_validate(data)
        assert ast.record_type == "transcript"
        assert ast.root.search_name == "GenesByTaxon"
        assert ast.root.parameters == {"organism": "pfal"}

    def test_combine_step(self) -> None:
        data = {
            "recordType": "transcript",
            "root": {
                "searchName": "bq",
                "parameters": {},
                "operator": "INTERSECT",
                "primaryInput": {
                    "searchName": "S1",
                    "parameters": {"a": "1"},
                },
                "secondaryInput": {
                    "searchName": "S2",
                    "parameters": {"b": "2"},
                },
            },
        }
        ast = StrategyAST.model_validate(data)
        assert ast.root.operator == CombineOp.INTERSECT
        assert ast.root.primary_input is not None
        assert ast.root.secondary_input is not None

    def test_missing_record_type_raises(self) -> None:
        with pytest.raises(PydanticValidationError):
            StrategyAST.model_validate({"root": {"searchName": "S1"}})

    def test_missing_root_raises(self) -> None:
        with pytest.raises(PydanticValidationError):
            StrategyAST.model_validate({"recordType": "transcript"})

    def test_missing_search_name_raises(self) -> None:
        with pytest.raises(PydanticValidationError):
            StrategyAST.model_validate(
                {"recordType": "transcript", "root": {"parameters": {}}}
            )

    def test_secondary_without_primary_raises(self) -> None:
        with pytest.raises(PydanticValidationError, match="primaryInput"):
            StrategyAST.model_validate(
                {
                    "recordType": "transcript",
                    "root": {
                        "searchName": "bq",
                        "secondaryInput": {"searchName": "S2"},
                    },
                }
            )

    def test_secondary_without_operator_raises(self) -> None:
        with pytest.raises(PydanticValidationError, match="operator"):
            StrategyAST.model_validate(
                {
                    "recordType": "transcript",
                    "root": {
                        "searchName": "bq",
                        "primaryInput": {"searchName": "S1"},
                        "secondaryInput": {"searchName": "S2"},
                    },
                }
            )

    def test_colocate_without_params_raises(self) -> None:
        with pytest.raises(PydanticValidationError, match="colocationParams"):
            StrategyAST.model_validate(
                {
                    "recordType": "transcript",
                    "root": {
                        "searchName": "bq",
                        "operator": "COLOCATE",
                        "primaryInput": {"searchName": "S1"},
                        "secondaryInput": {"searchName": "S2"},
                    },
                }
            )

    def test_colocation_params_on_non_colocate_raises(self) -> None:
        with pytest.raises(PydanticValidationError, match="colocationParams"):
            StrategyAST.model_validate(
                {
                    "recordType": "transcript",
                    "root": {
                        "searchName": "bq",
                        "operator": "INTERSECT",
                        "primaryInput": {"searchName": "S1"},
                        "secondaryInput": {"searchName": "S2"},
                        "colocationParams": {"upstream": 1000},
                    },
                }
            )

    def test_round_trip_preserves_structure(self) -> None:
        """to_dict -> model_validate should preserve key fields."""
        original = StrategyAST(
            record_type="transcript",
            root=PlanStepNode(
                search_name="GenesByTaxon",
                parameters={"organism": "pfal"},
                id="step1",
            ),
            name="Test Strategy",
            description="A test",
        )
        data = original.to_dict()
        restored = StrategyAST.model_validate(data)
        assert restored.record_type == original.record_type
        assert restored.root.search_name == original.root.search_name
        assert restored.root.parameters == original.root.parameters
        assert restored.name == original.name
        assert restored.description == original.description

    def test_with_filters(self) -> None:
        data = {
            "recordType": "transcript",
            "root": {
                "searchName": "S1",
                "parameters": {},
                "filters": [{"name": "gene_type", "value": "protein_coding"}],
            },
        }
        ast = StrategyAST.model_validate(data)
        assert len(ast.root.filters) == 1
        assert ast.root.filters[0].name == "gene_type"

    def test_with_analyses(self) -> None:
        data = {
            "recordType": "transcript",
            "root": {
                "searchName": "S1",
                "parameters": {},
                "analyses": [
                    {"analysisType": "go_enrichment", "parameters": {"ont": "BP"}}
                ],
            },
        }
        ast = StrategyAST.model_validate(data)
        assert len(ast.root.analyses) == 1
        assert ast.root.analyses[0].analysis_type == "go_enrichment"

    def test_with_wdk_weight(self) -> None:
        data = {
            "recordType": "transcript",
            "root": {
                "searchName": "S1",
                "parameters": {},
                "wdkWeight": 10,
            },
        }
        ast = StrategyAST.model_validate(data)
        assert ast.root.wdk_weight == 10
