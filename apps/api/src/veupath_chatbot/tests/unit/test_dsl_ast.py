"""Tests for strategy DSL AST serialization."""

import pytest

from veupath_chatbot.domain.strategy.ast import (
    PlanStepNode,
    StepAnalysis,
    StepFilter,
    StepReport,
    StrategyAST,
    from_dict,
    generate_step_id,
)
from veupath_chatbot.domain.strategy.ops import ColocationParams, CombineOp


class TestInferKind:
    def test_search_node(self) -> None:
        node = PlanStepNode(search_name="GenesByTextSearch")
        assert node.infer_kind() == "search"

    def test_transform_node(self) -> None:
        child = PlanStepNode(search_name="GenesByTextSearch")
        node = PlanStepNode(search_name="GenesByOrthology", primary_input=child)
        assert node.infer_kind() == "transform"

    def test_combine_node(self) -> None:
        left = PlanStepNode(search_name="GenesByTextSearch")
        right = PlanStepNode(search_name="GenesByGoTerm")
        node = PlanStepNode(
            search_name="boolean",
            primary_input=left,
            secondary_input=right,
            operator=CombineOp.INTERSECT,
        )
        assert node.infer_kind() == "combine"


class TestGetAllSteps:
    def test_single_step(self) -> None:
        root = PlanStepNode(search_name="S1", id="s1")
        ast = StrategyAST(record_type="gene", root=root)
        steps = ast.get_all_steps()
        assert len(steps) == 1
        assert steps[0].id == "s1"

    def test_tree_depth_first_order(self) -> None:
        left = PlanStepNode(search_name="S1", id="left")
        right = PlanStepNode(search_name="S2", id="right")
        root = PlanStepNode(
            search_name="bool",
            primary_input=left,
            secondary_input=right,
            operator=CombineOp.UNION,
            id="root",
        )
        ast = StrategyAST(record_type="gene", root=root)
        ids = [s.id for s in ast.get_all_steps()]
        # depth-first: left, right, then root
        assert ids == ["left", "right", "root"]


class TestGetStepById:
    def test_finds_existing(self) -> None:
        child = PlanStepNode(search_name="S1", id="child")
        root = PlanStepNode(search_name="T1", primary_input=child, id="root")
        ast = StrategyAST(record_type="gene", root=root)
        assert ast.get_step_by_id("child") is child

    def test_returns_none_for_missing(self) -> None:
        root = PlanStepNode(search_name="S1", id="root")
        ast = StrategyAST(record_type="gene", root=root)
        assert ast.get_step_by_id("nonexistent") is None


class TestFromDictErrors:
    def test_missing_record_type(self) -> None:
        with pytest.raises(TypeError, match="recordType"):
            from_dict({"root": {"searchName": "S1"}})

    def test_missing_root(self) -> None:
        with pytest.raises(TypeError, match="root"):
            from_dict({"recordType": "gene"})

    def test_missing_search_name(self) -> None:
        with pytest.raises(ValueError, match="searchName"):
            from_dict({"recordType": "gene", "root": {"parameters": {}}})

    def test_invalid_parameters_type(self) -> None:
        with pytest.raises(TypeError, match="parameters"):
            from_dict(
                {
                    "recordType": "gene",
                    "root": {"searchName": "S1", "parameters": "bad"},
                }
            )

    def test_secondary_without_primary(self) -> None:
        with pytest.raises(ValueError, match="primaryInput"):
            from_dict(
                {
                    "recordType": "gene",
                    "root": {
                        "searchName": "bool",
                        "secondaryInput": {"searchName": "S2"},
                    },
                }
            )

    def test_secondary_without_operator(self) -> None:
        with pytest.raises(ValueError, match="operator"):
            from_dict(
                {
                    "recordType": "gene",
                    "root": {
                        "searchName": "bool",
                        "primaryInput": {"searchName": "S1"},
                        "secondaryInput": {"searchName": "S2"},
                    },
                }
            )

    def test_colocate_without_params(self) -> None:
        with pytest.raises(ValueError, match="colocationParams"):
            from_dict(
                {
                    "recordType": "gene",
                    "root": {
                        "searchName": "bool",
                        "primaryInput": {"searchName": "S1"},
                        "secondaryInput": {"searchName": "S2"},
                        "operator": "COLOCATE",
                    },
                }
            )

    def test_colocation_params_on_non_colocate(self) -> None:
        with pytest.raises(ValueError, match="colocationParams"):
            from_dict(
                {
                    "recordType": "gene",
                    "root": {
                        "searchName": "bool",
                        "primaryInput": {"searchName": "S1"},
                        "secondaryInput": {"searchName": "S2"},
                        "operator": "INTERSECT",
                        "colocationParams": {"upstream": 100, "downstream": 200},
                    },
                }
            )


class TestFromDictColocation:
    def test_valid_colocation_round_trip(self) -> None:
        data = {
            "recordType": "gene",
            "root": {
                "searchName": "bool",
                "primaryInput": {"searchName": "S1"},
                "secondaryInput": {"searchName": "S2"},
                "operator": "COLOCATE",
                "colocationParams": {
                    "upstream": 1000,
                    "downstream": 500,
                    "strand": "same",
                },
            },
        }
        ast = from_dict(data)
        cp = ast.root.colocation_params
        assert cp is not None
        assert cp.upstream == 1000
        assert cp.downstream == 500
        assert cp.strand == "same"

    def test_defaults_strand_to_both(self) -> None:
        data = {
            "recordType": "gene",
            "root": {
                "searchName": "bool",
                "primaryInput": {"searchName": "S1"},
                "secondaryInput": {"searchName": "S2"},
                "operator": "COLOCATE",
                "colocationParams": {"upstream": 0, "downstream": 0},
            },
        }
        ast = from_dict(data)
        assert ast.root.colocation_params is not None
        assert ast.root.colocation_params.strand == "both"

    def test_invalid_strand_defaults_to_both(self) -> None:
        data = {
            "recordType": "gene",
            "root": {
                "searchName": "bool",
                "primaryInput": {"searchName": "S1"},
                "secondaryInput": {"searchName": "S2"},
                "operator": "COLOCATE",
                "colocationParams": {"upstream": 0, "downstream": 0, "strand": "bogus"},
            },
        }
        ast = from_dict(data)
        assert ast.root.colocation_params is not None
        assert ast.root.colocation_params.strand == "both"


class TestFromDictMetadata:
    def test_name_and_description_from_metadata(self) -> None:
        data = {
            "recordType": "gene",
            "root": {"searchName": "S1"},
            "metadata": {"name": "My Strategy", "description": "Find kinases"},
        }
        ast = from_dict(data)
        assert ast.name == "My Strategy"
        assert ast.description == "Find kinases"

    def test_missing_metadata_gives_none(self) -> None:
        data = {"recordType": "gene", "root": {"searchName": "S1"}}
        ast = from_dict(data)
        assert ast.name is None
        assert ast.description is None


class TestToDictRoundTrip:
    def test_step_attachments_round_trip(self) -> None:
        """Ensure filters, analyses, and reports serialize in plans."""
        search = PlanStepNode(
            search_name="GenesByTextSearch",
            parameters={"text": "kinase"},
            filters=[StepFilter(name="ranked", value={"min": 5})],
            analyses=[
                StepAnalysis(
                    analysis_type="enrichment",
                    parameters={"dataset": "GO"},
                    custom_name="GO enrichment",
                )
            ],
            reports=[
                StepReport(report_name="standard", config={"attributes": ["gene_id"]})
            ],
        )
        transform = PlanStepNode(
            search_name="GenesByOrthology",
            primary_input=search,
            parameters={"taxon": "Toxoplasma"},
            filters=[StepFilter(name="score", value=0.8)],
        )
        combine = PlanStepNode(
            search_name="boolean_question_gene",
            operator=CombineOp.INTERSECT,
            primary_input=search,
            secondary_input=transform,
            reports=[StepReport(report_name="fullRecord", config={"format": "json"})],
        )
        strategy = StrategyAST(record_type="gene", root=combine, name="Test")

        payload = strategy.to_dict()
        parsed = from_dict(payload)

        root = parsed.root
        assert root.infer_kind() == "combine"
        assert root.reports
        assert root.reports[0].report_name == "fullRecord"
        assert root.primary_input is not None
        assert root.primary_input.infer_kind() == "search"
        assert root.primary_input.filters[0].name == "ranked"
        assert root.primary_input.analyses[0].analysis_type == "enrichment"
        assert root.secondary_input is not None
        assert root.secondary_input.infer_kind() == "transform"
        assert root.secondary_input.filters[0].name == "score"

    def test_colocation_round_trip(self) -> None:
        left = PlanStepNode(search_name="S1")
        right = PlanStepNode(search_name="S2")
        root = PlanStepNode(
            search_name="bool",
            primary_input=left,
            secondary_input=right,
            operator=CombineOp.COLOCATE,
            colocation_params=ColocationParams(
                upstream=100, downstream=200, strand="opposite"
            ),
        )
        ast = StrategyAST(record_type="gene", root=root)
        payload = ast.to_dict()
        parsed = from_dict(payload)
        cp = parsed.root.colocation_params
        assert cp is not None
        assert cp.upstream == 100
        assert cp.downstream == 200
        assert cp.strand == "opposite"


class TestGenerateStepId:
    def test_format(self) -> None:
        step_id = generate_step_id()
        assert step_id.startswith("step_")
        assert len(step_id) == 13  # "step_" + 8 hex chars

    def test_unique(self) -> None:
        ids = {generate_step_id() for _ in range(100)}
        assert len(ids) == 100


class TestStepFilterToDict:
    def test_serializes(self) -> None:
        f = StepFilter(name="ranked", value={"min": 5}, disabled=True)
        d = f.to_dict()
        assert d == {"name": "ranked", "value": {"min": 5}, "disabled": True}

    def test_disabled_defaults_false(self) -> None:
        f = StepFilter(name="f1", value=1)
        assert f.to_dict()["disabled"] is False


class TestStepAnalysisToDict:
    def test_serializes_with_custom_name(self) -> None:
        a = StepAnalysis(
            analysis_type="enrichment",
            parameters={"go": "yes"},
            custom_name="GO enrichment",
        )
        d = a.to_dict()
        assert d["analysisType"] == "enrichment"
        assert d["parameters"] == {"go": "yes"}
        assert d["customName"] == "GO enrichment"

    def test_omits_custom_name_when_none(self) -> None:
        a = StepAnalysis(analysis_type="word", parameters={})
        d = a.to_dict()
        assert "customName" not in d

    def test_omits_custom_name_when_empty(self) -> None:
        a = StepAnalysis(analysis_type="word", parameters={}, custom_name="")
        d = a.to_dict()
        assert "customName" not in d


class TestStepReportToDict:
    def test_serializes(self) -> None:
        r = StepReport(report_name="tabular", config={"sep": ","})
        d = r.to_dict()
        assert d == {"reportName": "tabular", "config": {"sep": ","}}

    def test_defaults(self) -> None:
        r = StepReport()
        d = r.to_dict()
        assert d["reportName"] == "standard"
        assert d["config"] == {}


class TestPlanStepNodeToDict:
    def test_search_node_to_dict(self) -> None:
        node = PlanStepNode(search_name="S1", parameters={"x": "1"}, id="s1")
        d = node.to_dict()
        assert d["id"] == "s1"
        assert d["searchName"] == "S1"
        assert d["displayName"] == "S1"  # defaults to search_name
        assert d["parameters"] == {"x": "1"}
        assert "primaryInput" not in d
        assert "secondaryInput" not in d
        assert "operator" not in d
        assert "colocationParams" not in d
        assert "filters" not in d
        assert "analyses" not in d
        assert "reports" not in d

    def test_display_name_used_when_set(self) -> None:
        node = PlanStepNode(search_name="S1", display_name="Custom", id="s1")
        assert node.to_dict()["displayName"] == "Custom"

    def test_empty_parameters_still_dict(self) -> None:
        node = PlanStepNode(search_name="S1", id="s1")
        assert node.to_dict()["parameters"] == {}


class TestStrategyASTToDict:
    def test_metadata_includes_name_and_description(self) -> None:
        root = PlanStepNode(search_name="S1", id="s1")
        ast = StrategyAST(
            record_type="gene",
            root=root,
            name="Test",
            description="A description",
        )
        d = ast.to_dict()
        assert d["recordType"] == "gene"
        metadata = d["metadata"]
        assert isinstance(metadata, dict)
        assert metadata["name"] == "Test"
        assert metadata["description"] == "A description"

    def test_no_metadata_when_empty(self) -> None:
        root = PlanStepNode(search_name="S1", id="s1")
        ast = StrategyAST(record_type="gene", root=root)
        d = ast.to_dict()
        assert d["metadata"] is None

    def test_metadata_preserves_extra_fields(self) -> None:
        root = PlanStepNode(search_name="S1", id="s1")
        ast = StrategyAST(
            record_type="gene",
            root=root,
            name="Test",
            metadata={"custom_key": "custom_value"},
        )
        d = ast.to_dict()
        metadata = d["metadata"]
        assert isinstance(metadata, dict)
        assert metadata["custom_key"] == "custom_value"
        assert metadata["name"] == "Test"


class TestFromDictStepId:
    def test_preserves_explicit_id(self) -> None:
        data = {
            "recordType": "gene",
            "root": {"searchName": "S1", "id": "explicit_id"},
        }
        ast = from_dict(data)
        assert ast.root.id == "explicit_id"

    def test_generates_id_when_missing(self) -> None:
        data = {"recordType": "gene", "root": {"searchName": "S1"}}
        ast = from_dict(data)
        assert ast.root.id.startswith("step_")

    def test_non_string_metadata_ignored(self) -> None:
        data = {
            "recordType": "gene",
            "root": {"searchName": "S1"},
            "metadata": {"name": 123, "description": True},
        }
        ast = from_dict(data)
        assert ast.name is None
        assert ast.description is None

    def test_non_dict_metadata_ignored(self) -> None:
        data = {
            "recordType": "gene",
            "root": {"searchName": "S1"},
            "metadata": "not a dict",
        }
        ast = from_dict(data)
        assert ast.name is None
        assert ast.description is None

    def test_display_name_parsed(self) -> None:
        data = {
            "recordType": "gene",
            "root": {"searchName": "S1", "displayName": "My Search"},
        }
        ast = from_dict(data)
        assert ast.root.display_name == "My Search"

    def test_non_string_display_name_ignored(self) -> None:
        data = {
            "recordType": "gene",
            "root": {"searchName": "S1", "displayName": 42},
        }
        ast = from_dict(data)
        assert ast.root.display_name is None


class TestGetAllStepsDeep:
    def test_three_level_tree(self) -> None:
        s1 = PlanStepNode(search_name="S1", id="s1")
        s2 = PlanStepNode(search_name="S2", id="s2")
        t1 = PlanStepNode(search_name="T1", primary_input=s2, id="t1")
        root = PlanStepNode(
            search_name="bool",
            primary_input=s1,
            secondary_input=t1,
            operator=CombineOp.UNION,
            id="root",
        )
        ast = StrategyAST(record_type="gene", root=root)
        ids = [s.id for s in ast.get_all_steps()]
        # depth-first: s1, s2, t1, root
        assert ids == ["s1", "s2", "t1", "root"]

    def test_get_step_by_id_deep(self) -> None:
        s1 = PlanStepNode(search_name="S1", id="s1")
        s2 = PlanStepNode(search_name="S2", id="s2")
        root = PlanStepNode(
            search_name="bool",
            primary_input=s1,
            secondary_input=s2,
            operator=CombineOp.INTERSECT,
            id="root",
        )
        ast = StrategyAST(record_type="gene", root=root)
        assert ast.get_step_by_id("s2") is s2
        assert ast.get_step_by_id("root") is root
