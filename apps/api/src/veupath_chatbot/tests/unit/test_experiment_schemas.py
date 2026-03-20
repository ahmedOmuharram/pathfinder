"""Unit tests for experiment Pydantic request/response schemas."""

import pytest
from pydantic import ValidationError

from veupath_chatbot.transport.http.schemas.experiments import (
    BenchmarkControlSet,
    CreateExperimentRequest,
    CustomEnrichRequest,
    OperatorKnobRequest,
    RefineRequest,
    RunCrossValidationRequest,
    RunEnrichmentRequest,
    ThresholdKnobRequest,
    ThresholdSweepRequest,
)


class TestCreateExperimentRequest:
    def test_minimal_valid_request(self) -> None:
        req = CreateExperimentRequest(
            siteId="plasmodb",
            recordType="gene",
            searchName="GenesByTextSearch",
            positiveControls=["g1", "g2"],
            negativeControls=["n1"],
            controlsSearchName="GeneByLocusTag",
            controlsParamName="single_gene_id",
        )
        assert req.site_id == "plasmodb"
        assert req.mode == "single"
        assert req.name == "Untitled Experiment"
        assert req.enable_cross_validation is False

    def test_full_request_with_all_fields(self) -> None:
        req = CreateExperimentRequest(
            siteId="toxodb",
            recordType="gene",
            mode="multi-step",
            searchName="",
            parameters={},
            stepTree={"id": "s1", "searchName": "Test"},
            positiveControls=["g1"],
            negativeControls=["n1"],
            controlsSearchName="GeneByLocusTag",
            controlsParamName="single_gene_id",
            controlsValueFormat="json_list",
            enableCrossValidation=True,
            kFolds=3,
            enrichmentTypes=["go_function", "pathway"],
            name="My Experiment",
            description="Testing",
            enableStepAnalysis=True,
            stepAnalysisPhases=["step_evaluation", "contribution"],
            sortAttribute="score",
            sortDirection="DESC",
            parentExperimentId="exp_parent_001",
        )
        assert req.mode == "multi-step"
        assert req.enable_cross_validation is True
        assert req.k_folds == 3
        assert req.enrichment_types == ["go_function", "pathway"]
        assert req.parent_experiment_id == "exp_parent_001"

    def test_snake_case_field_names_accepted(self) -> None:
        """populate_by_name=True allows snake_case."""
        req = CreateExperimentRequest(
            site_id="plasmodb",
            record_type="gene",
            search_name="Test",
            positive_controls=["g1"],
            negative_controls=["n1"],
            controls_search_name="GeneByLocusTag",
            controls_param_name="single_gene_id",
        )
        assert req.site_id == "plasmodb"

    def test_k_folds_validation(self) -> None:
        with pytest.raises(ValidationError):
            CreateExperimentRequest(
                siteId="plasmodb",
                recordType="gene",
                positiveControls=["g1"],
                negativeControls=["n1"],
                controlsSearchName="GeneByLocusTag",
                controlsParamName="single_gene_id",
                kFolds=1,  # min is 2
            )

    def test_name_max_length(self) -> None:
        with pytest.raises(ValidationError):
            CreateExperimentRequest(
                siteId="plasmodb",
                recordType="gene",
                positiveControls=["g1"],
                negativeControls=["n1"],
                controlsSearchName="GeneByLocusTag",
                controlsParamName="single_gene_id",
                name="x" * 201,
            )


class TestThresholdKnobRequest:
    def test_valid_knob(self) -> None:
        knob = ThresholdKnobRequest(
            stepId="step_1",
            paramName="evalue_threshold",
            minVal=0.0,
            maxVal=1.0,
            stepSize=0.1,
        )
        assert knob.step_id == "step_1"
        assert knob.param_name == "evalue_threshold"
        assert knob.step_size == 0.1

    def test_defaults(self) -> None:
        knob = ThresholdKnobRequest(stepId="s1", paramName="p1")
        assert knob.min_val == 0
        assert knob.max_val == 1
        assert knob.step_size is None


class TestOperatorKnobRequest:
    def test_valid_knob(self) -> None:
        knob = OperatorKnobRequest(
            combineNodeId="combine_1",
            options=["INTERSECT", "UNION"],
        )
        assert knob.combine_node_id == "combine_1"
        assert knob.options == ["INTERSECT", "UNION"]

    def test_default_options(self) -> None:
        knob = OperatorKnobRequest(combineNodeId="c1")
        assert "INTERSECT" in knob.options
        assert "UNION" in knob.options
        assert "MINUS" in knob.options


class TestThresholdSweepRequest:
    def test_valid_sweep(self) -> None:
        req = ThresholdSweepRequest(
            parameterName="evalue",
            minValue=0.0,
            maxValue=1.0,
            steps=10,
        )
        assert req.parameter_name == "evalue"
        assert req.steps == 10

    def test_steps_validation(self) -> None:
        with pytest.raises(ValidationError):
            ThresholdSweepRequest(
                parameterName="evalue",
                minValue=0.0,
                maxValue=1.0,
                steps=2,  # min is 3
            )


class TestRunCrossValidationRequest:
    def test_defaults(self) -> None:
        req = RunCrossValidationRequest()
        assert req.k_folds == 5

    def test_k_folds_bounds(self) -> None:
        req = RunCrossValidationRequest(kFolds=10)
        assert req.k_folds == 10

        with pytest.raises(ValidationError):
            RunCrossValidationRequest(kFolds=11)


class TestRunEnrichmentRequest:
    def test_valid_types(self) -> None:
        req = RunEnrichmentRequest(
            enrichmentTypes=["go_function", "pathway"],
        )
        assert len(req.enrichment_types) == 2


class TestCustomEnrichRequest:
    def test_valid_request(self) -> None:
        req = CustomEnrichRequest(
            geneSetName="Kinases",
            geneIds=["g1", "g2", "g3"],
        )
        assert req.gene_set_name == "Kinases"
        assert len(req.gene_ids) == 3

    def test_empty_gene_ids_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CustomEnrichRequest(
                geneSetName="Kinases",
                geneIds=[],
            )


class TestRefineRequest:
    def test_combine_action(self) -> None:
        req = RefineRequest(
            action="combine",
            searchName="GenesByBlast",
            parameters={"query": "ATCG"},
            operator="INTERSECT",
        )
        assert req.action == "combine"

    def test_transform_action(self) -> None:
        req = RefineRequest(
            action="transform",
            transformName="gene-to-ortholog",
        )
        assert req.action == "transform"

    def test_invalid_action(self) -> None:
        with pytest.raises(ValidationError):
            RefineRequest(action="invalid")


class TestBenchmarkControlSet:
    def test_valid_set(self) -> None:
        cs = BenchmarkControlSet(
            label="Published Set",
            positiveControls=["g1", "g2"],
            negativeControls=["n1"],
            isPrimary=True,
        )
        assert cs.label == "Published Set"
        assert cs.is_primary is True
