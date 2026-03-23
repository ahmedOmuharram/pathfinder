"""Tests for strategy DSL AST domain logic and round-trip serialization."""

import pytest
from pydantic import ValidationError as PydanticValidationError

from veupath_chatbot.domain.strategy.ast import (
    PlanStepNode,
    StepAnalysis,
    StepFilter,
    StepReport,
    generate_step_id,
    walk_step_tree,
)
from veupath_chatbot.domain.strategy.ops import ColocationParams, CombineOp
from veupath_chatbot.transport.http.schemas.strategies import StrategyPlanPayload


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


class TestWalkStepTree:
    def test_single_step(self) -> None:
        root = PlanStepNode(search_name="S1", id="s1")
        steps = walk_step_tree(root)
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
        ids = [s.id for s in walk_step_tree(root)]
        # depth-first: left, right, then root
        assert ids == ["left", "right", "root"]


class TestFindStepById:
    def test_finds_existing(self) -> None:
        child = PlanStepNode(search_name="S1", id="child")
        root = PlanStepNode(search_name="T1", primary_input=child, id="root")
        steps = walk_step_tree(root)
        found = next((s for s in steps if s.id == "child"), None)
        assert found is child

    def test_returns_none_for_missing(self) -> None:
        root = PlanStepNode(search_name="S1", id="root")
        steps = walk_step_tree(root)
        found = next((s for s in steps if s.id == "nonexistent"), None)
        assert found is None


class TestModelValidateErrors:
    def test_missing_record_type(self) -> None:
        with pytest.raises(PydanticValidationError):
            StrategyPlanPayload.model_validate({"root": {"searchName": "S1"}})

    def test_missing_root(self) -> None:
        with pytest.raises(PydanticValidationError):
            StrategyPlanPayload.model_validate({"recordType": "gene"})

    def test_missing_search_name(self) -> None:
        with pytest.raises(PydanticValidationError):
            StrategyPlanPayload.model_validate(
                {"recordType": "gene", "root": {"parameters": {}}}
            )

    def test_invalid_parameters_type(self) -> None:
        with pytest.raises(PydanticValidationError):
            StrategyPlanPayload.model_validate(
                {
                    "recordType": "gene",
                    "root": {"searchName": "S1", "parameters": "bad"},
                }
            )

    def test_secondary_without_primary(self) -> None:
        with pytest.raises(PydanticValidationError, match="primaryInput"):
            StrategyPlanPayload.model_validate(
                {
                    "recordType": "gene",
                    "root": {
                        "searchName": "bool",
                        "secondaryInput": {"searchName": "S2"},
                    },
                }
            )

    def test_secondary_without_operator(self) -> None:
        with pytest.raises(PydanticValidationError, match="operator"):
            StrategyPlanPayload.model_validate(
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
        with pytest.raises(PydanticValidationError, match="colocationParams"):
            StrategyPlanPayload.model_validate(
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
        with pytest.raises(PydanticValidationError, match="colocationParams"):
            StrategyPlanPayload.model_validate(
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


class TestModelValidateColocation:
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
        ast = StrategyPlanPayload.model_validate(data)
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
        ast = StrategyPlanPayload.model_validate(data)
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
        ast = StrategyPlanPayload.model_validate(data)
        assert ast.root.colocation_params is not None
        assert ast.root.colocation_params.strand == "both"


class TestModelValidateMetadata:
    def test_name_and_description_from_top_level(self) -> None:
        data = {
            "recordType": "gene",
            "root": {"searchName": "S1"},
            "name": "My Strategy",
            "description": "Find kinases",
        }
        ast = StrategyPlanPayload.model_validate(data)
        assert ast.name == "My Strategy"
        assert ast.description == "Find kinases"

    def test_missing_name_gives_none(self) -> None:
        data = {"recordType": "gene", "root": {"searchName": "S1"}}
        ast = StrategyPlanPayload.model_validate(data)
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
        strategy = StrategyPlanPayload(record_type="gene", root=combine, name="Test")

        payload = strategy.model_dump(by_alias=True, exclude_none=True, mode="json")
        parsed = StrategyPlanPayload.model_validate(payload)

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
        ast = StrategyPlanPayload(record_type="gene", root=root)
        payload = ast.model_dump(by_alias=True, exclude_none=True, mode="json")
        parsed = StrategyPlanPayload.model_validate(payload)
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


class TestPlanStepNodeDisplayName:
    def test_display_name_none_by_default(self) -> None:
        node = PlanStepNode(search_name="GenesByTaxon", id="s1")
        assert node.display_name is None

    def test_display_name_preserved_when_set(self) -> None:
        node = PlanStepNode(
            search_name="GenesByTaxon", display_name="Organism", id="s1"
        )
        assert node.display_name == "Organism"


class TestStrategyPlanPayloadToDict:
    def test_name_and_description_at_top_level(self) -> None:
        root = PlanStepNode(search_name="S1", id="s1")
        ast = StrategyPlanPayload(
            record_type="gene",
            root=root,
            name="Test",
            description="A description",
        )
        d = ast.model_dump(by_alias=True, exclude_none=True, mode="json")
        assert d["recordType"] == "gene"
        assert d["name"] == "Test"
        assert d["description"] == "A description"

    def test_metadata_preserves_extra_fields(self) -> None:
        root = PlanStepNode(search_name="S1", id="s1")
        ast = StrategyPlanPayload(
            record_type="gene",
            root=root,
            name="Test",
            metadata={"custom_key": "custom_value"},
        )
        d = ast.model_dump(by_alias=True, exclude_none=True, mode="json")
        assert d["name"] == "Test"
        metadata = d["metadata"]
        assert isinstance(metadata, dict)
        assert metadata["custom_key"] == "custom_value"


class TestModelValidateStepId:
    def test_preserves_explicit_id(self) -> None:
        data = {
            "recordType": "gene",
            "root": {"searchName": "S1", "id": "explicit_id"},
        }
        ast = StrategyPlanPayload.model_validate(data)
        assert ast.root.id == "explicit_id"

    def test_generates_id_when_missing(self) -> None:
        data = {"recordType": "gene", "root": {"searchName": "S1"}}
        ast = StrategyPlanPayload.model_validate(data)
        assert ast.root.id.startswith("step_")

    def test_name_and_description_from_top_level(self) -> None:
        data = {
            "recordType": "gene",
            "root": {"searchName": "S1"},
            "name": "My Strategy",
            "description": "Find kinases",
        }
        ast = StrategyPlanPayload.model_validate(data)
        assert ast.name == "My Strategy"
        assert ast.description == "Find kinases"

    def test_display_name_parsed(self) -> None:
        data = {
            "recordType": "gene",
            "root": {"searchName": "S1", "displayName": "My Search"},
        }
        ast = StrategyPlanPayload.model_validate(data)
        assert ast.root.display_name == "My Search"


class TestWalkStepTreeDeep:
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
        ids = [s.id for s in walk_step_tree(root)]
        # depth-first: s1, s2, t1, root
        assert ids == ["s1", "s2", "t1", "root"]

    def test_find_step_by_id_deep(self) -> None:
        s1 = PlanStepNode(search_name="S1", id="s1")
        s2 = PlanStepNode(search_name="S2", id="s2")
        root = PlanStepNode(
            search_name="bool",
            primary_input=s1,
            secondary_input=s2,
            operator=CombineOp.INTERSECT,
            id="root",
        )
        steps = walk_step_tree(root)
        assert next(s for s in steps if s.id == "s2") is s2
        assert next(s for s in steps if s.id == "root") is root
