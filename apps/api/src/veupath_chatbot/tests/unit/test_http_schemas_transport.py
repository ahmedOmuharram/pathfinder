"""Tests for transport/http schema validators, constraints, and custom behavior.

Only tests OUR code: Field constraints (min_length, max_length, ge, le),
Literal validators, model_validators, extra-field configs, and SSE helpers.
Pydantic's own model_dump/model_validate/construction is not tested.
"""

import json

import pytest
from pydantic import ValidationError

from veupath_chatbot.transport.http.schemas.chat import ChatMention, ChatRequest
from veupath_chatbot.transport.http.schemas.experiments import (
    BenchmarkControlSet,
    CreateBatchExperimentRequest,
    CreateBenchmarkRequest,
    CreateExperimentRequest,
    CustomEnrichRequest,
    EnrichmentCompareRequest,
    OptimizationSpecRequest,
    OverlapRequest,
    RefineRequest,
    RunAnalysisRequest,
    RunCrossValidationRequest,
    RunEnrichmentRequest,
    ThresholdSweepRequest,
)
from veupath_chatbot.transport.http.schemas.gene_sets import (
    CreateGeneSetRequest,
    SetOperationRequest,
)
from veupath_chatbot.transport.http.schemas.plan import (
    BasePlanNode,
    ColocationParams,
    PlanNode,
    StrategyPlan,
)
from veupath_chatbot.transport.http.schemas.sites import SearchDetailsResponse
from veupath_chatbot.transport.http.schemas.strategies import (
    CreateStrategyRequest,
    UpdateStrategyRequest,
)
from veupath_chatbot.transport.http.sse import SSE_HEADERS, sse_stream

# ── Chat schema constraints ──────────────────────────────────────────────────


class TestChatMentionConstraints:
    def test_invalid_type_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ChatMention(type="invalid", id="x", displayName="X")  # type: ignore[arg-type]


class TestChatRequestConstraints:
    def test_message_max_length(self) -> None:
        ChatRequest(siteId="x", message="a" * 200_000)
        with pytest.raises(ValidationError):
            ChatRequest(siteId="x", message="a" * 200_001)

    def test_provider_literal(self) -> None:
        ChatRequest(siteId="x", message="hi", provider="anthropic")
        with pytest.raises(ValidationError):
            ChatRequest(siteId="x", message="hi", provider="invalid_provider")  # type: ignore[arg-type]

    def test_reasoning_effort_literal(self) -> None:
        ChatRequest(siteId="x", message="hi", reasoningEffort="high")
        with pytest.raises(ValidationError):
            ChatRequest(siteId="x", message="hi", reasoningEffort="ultra")  # type: ignore[arg-type]


# ── Plan schema validators ───────────────────────────────────────────────────


class TestColocationParamsConstraints:
    def test_negative_upstream_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ColocationParams(upstream=-1, downstream=0)

    def test_negative_downstream_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ColocationParams(upstream=0, downstream=-1)


class TestPlanNodeValidators:
    """Tests for model_validator rules on PlanNode."""

    def test_secondary_without_primary_rejected(self) -> None:
        leaf = PlanNode(searchName="A")
        with pytest.raises(
            ValidationError, match="secondaryInput requires primaryInput"
        ):
            PlanNode(searchName="X", secondaryInput=leaf)

    def test_secondary_without_operator_rejected(self) -> None:
        leaf1 = PlanNode(searchName="A")
        leaf2 = PlanNode(searchName="B")
        with pytest.raises(
            ValidationError, match="operator is required when secondaryInput"
        ):
            PlanNode(searchName="C", primaryInput=leaf1, secondaryInput=leaf2)

    def test_colocate_requires_colocation_params(self) -> None:
        leaf1 = PlanNode(searchName="A")
        leaf2 = PlanNode(searchName="B")
        with pytest.raises(
            ValidationError,
            match="colocationParams is required when operator is COLOCATE",
        ):
            PlanNode(
                searchName="C",
                primaryInput=leaf1,
                secondaryInput=leaf2,
                operator="COLOCATE",
            )

    def test_colocation_params_only_with_colocate(self) -> None:
        leaf1 = PlanNode(searchName="A")
        leaf2 = PlanNode(searchName="B")
        with pytest.raises(
            ValidationError,
            match="colocationParams is only allowed when operator is COLOCATE",
        ):
            PlanNode(
                searchName="C",
                primaryInput=leaf1,
                secondaryInput=leaf2,
                operator="INTERSECT",
                colocationParams=ColocationParams(upstream=100, downstream=100),
            )

    def test_colocate_with_params_succeeds(self) -> None:
        leaf1 = PlanNode(searchName="A")
        leaf2 = PlanNode(searchName="B")
        n = PlanNode(
            searchName="C",
            primaryInput=leaf1,
            secondaryInput=leaf2,
            operator="COLOCATE",
            colocationParams=ColocationParams(upstream=500, downstream=500),
        )
        assert n.colocationParams is not None


# ── Extra-field behavior ─────────────────────────────────────────────────────


class TestExtraFieldBehavior:
    """Tests for schemas with extra='allow' (WDK pass-through fields)."""

    def test_search_details_extra_fields(self) -> None:
        r = SearchDetailsResponse.model_validate({"custom_field": "value"})
        assert r.model_extra is not None
        assert r.model_extra.get("custom_field") == "value"

    def test_base_plan_node_extra_fields(self) -> None:
        n = BasePlanNode.model_validate({"wdkStepId": 42, "estimatedSize": 100})
        assert n.model_extra is not None
        assert n.model_extra.get("wdkStepId") == 42

    def test_plan_node_extra_fields(self) -> None:
        n = PlanNode.model_validate({"searchName": "X", "wdkStepId": 123})
        assert n.model_extra is not None
        assert n.model_extra.get("wdkStepId") == 123

    def test_strategy_plan_extra_fields(self) -> None:
        plan = StrategyPlan.model_validate(
            {"recordType": "gene", "root": {"searchName": "X"}, "customField": "yes"}
        )
        assert plan.model_extra is not None
        assert plan.model_extra.get("customField") == "yes"


# ── Strategy schema constraints ──────────────────────────────────────────────


class TestCreateStrategyRequestConstraints:
    def test_name_min_length(self) -> None:
        plan = StrategyPlan(recordType="gene", root=PlanNode(searchName="X"))
        with pytest.raises(ValidationError):
            CreateStrategyRequest(name="", siteId="x", plan=plan)

    def test_name_max_length(self) -> None:
        plan = StrategyPlan(recordType="gene", root=PlanNode(searchName="X"))
        CreateStrategyRequest(name="a" * 255, siteId="x", plan=plan)
        with pytest.raises(ValidationError):
            CreateStrategyRequest(name="a" * 256, siteId="x", plan=plan)


class TestUpdateStrategyRequestConstraints:
    def test_name_empty_rejected(self) -> None:
        with pytest.raises(ValidationError):
            UpdateStrategyRequest(name="")

    def test_name_too_long_rejected(self) -> None:
        with pytest.raises(ValidationError):
            UpdateStrategyRequest(name="x" * 256)


# ── Experiment schema constraints ────────────────────────────────────────────


def _exp_base(**overrides: object) -> dict:
    defaults: dict = {
        "siteId": "plasmodb",
        "recordType": "gene",
        "positiveControls": ["G1"],
        "negativeControls": ["G2"],
        "controlsSearchName": "GenesByLocusTag",
        "controlsParamName": "ds_gene_ids",
    }
    defaults.update(overrides)
    return defaults


class TestCreateExperimentRequestConstraints:
    def test_optimization_budget_bounds(self) -> None:
        CreateExperimentRequest(**_exp_base(optimizationBudget=5))
        CreateExperimentRequest(**_exp_base(optimizationBudget=200))
        with pytest.raises(ValidationError):
            CreateExperimentRequest(**_exp_base(optimizationBudget=4))
        with pytest.raises(ValidationError):
            CreateExperimentRequest(**_exp_base(optimizationBudget=201))

    def test_tree_optimization_budget_bounds(self) -> None:
        CreateExperimentRequest(**_exp_base(treeOptimizationBudget=5))
        with pytest.raises(ValidationError):
            CreateExperimentRequest(**_exp_base(treeOptimizationBudget=4))
        with pytest.raises(ValidationError):
            CreateExperimentRequest(**_exp_base(treeOptimizationBudget=201))

    def test_name_max_length(self) -> None:
        CreateExperimentRequest(**_exp_base(name="a" * 200))
        with pytest.raises(ValidationError):
            CreateExperimentRequest(**_exp_base(name="a" * 201))

    def test_description_max_length(self) -> None:
        CreateExperimentRequest(**_exp_base(description="x" * 2000))
        with pytest.raises(ValidationError):
            CreateExperimentRequest(**_exp_base(description="x" * 2001))

    def test_sort_direction_literal(self) -> None:
        for val in ("ASC", "DESC"):
            CreateExperimentRequest(**_exp_base(sortDirection=val))
        with pytest.raises(ValidationError):
            CreateExperimentRequest(**_exp_base(sortDirection="RANDOM"))

    def test_controls_value_format_literal(self) -> None:
        for fmt in ("newline", "json_list", "comma"):
            CreateExperimentRequest(**_exp_base(controlsValueFormat=fmt))
        with pytest.raises(ValidationError):
            CreateExperimentRequest(**_exp_base(controlsValueFormat="pipe"))

    def test_mode_literal(self) -> None:
        for mode in ("single", "multi-step", "import"):
            CreateExperimentRequest(**_exp_base(mode=mode))

    def test_optimization_objective_literal(self) -> None:
        for obj in ("f1", "recall", "precision", "mcc"):
            CreateExperimentRequest(**_exp_base(optimizationObjective=obj))
        with pytest.raises(ValidationError):
            CreateExperimentRequest(**_exp_base(optimizationObjective="invalid"))

    def test_missing_required_controls(self) -> None:
        with pytest.raises(ValidationError):
            CreateExperimentRequest(
                siteId="plasmodb",
                recordType="gene",
                controlsSearchName="X",
                controlsParamName="p",
            )


class TestOptimizationSpecRequestConstraints:
    def test_invalid_type_rejected(self) -> None:
        with pytest.raises(ValidationError):
            OptimizationSpecRequest(name="x", type="boolean")  # type: ignore[arg-type]


class TestCreateBatchExperimentRequestConstraints:
    def test_empty_targets_rejected(self) -> None:
        base = CreateExperimentRequest(**_exp_base())
        with pytest.raises(ValidationError):
            CreateBatchExperimentRequest(
                base=base, organismParamName="organism", targetOrganisms=[]
            )


class TestRunCrossValidationRequestConstraints:
    def test_k_folds_bounds(self) -> None:
        RunCrossValidationRequest(kFolds=2)
        RunCrossValidationRequest(kFolds=10)
        with pytest.raises(ValidationError):
            RunCrossValidationRequest(kFolds=1)
        with pytest.raises(ValidationError):
            RunCrossValidationRequest(kFolds=11)


class TestRunEnrichmentRequestConstraints:
    def test_invalid_type_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RunEnrichmentRequest(enrichmentTypes=["invalid_type"])


class TestThresholdSweepRequestConstraints:
    def test_invalid_sweep_type_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ThresholdSweepRequest(parameterName="x", sweepType="logarithmic")


class TestRunAnalysisRequestConstraints:
    def test_empty_name_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RunAnalysisRequest(analysisName="")


class TestRefineRequestConstraints:
    def test_invalid_action_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RefineRequest(action="delete")  # type: ignore[arg-type]


class TestCustomEnrichRequestConstraints:
    def test_empty_name_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CustomEnrichRequest(geneSetName="", geneIds=["G1"])

    def test_empty_gene_ids_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CustomEnrichRequest(geneSetName="X", geneIds=[])


class TestBenchmarkControlSetConstraints:
    def test_empty_label_rejected(self) -> None:
        with pytest.raises(ValidationError):
            BenchmarkControlSet(
                label="", positiveControls=["G1"], negativeControls=["G2"]
            )


class TestCreateBenchmarkRequestConstraints:
    def test_empty_control_sets_rejected(self) -> None:
        base = CreateExperimentRequest(**_exp_base())
        with pytest.raises(ValidationError):
            CreateBenchmarkRequest(base=base, controlSets=[])


class TestOverlapRequestConstraints:
    def test_min_length(self) -> None:
        OverlapRequest(experimentIds=["e1", "e2"])
        with pytest.raises(ValidationError):
            OverlapRequest(experimentIds=["e1"])


class TestEnrichmentCompareRequestConstraints:
    def test_min_length(self) -> None:
        EnrichmentCompareRequest(experimentIds=["e1", "e2"])
        with pytest.raises(ValidationError):
            EnrichmentCompareRequest(experimentIds=["e1"])


# ── Gene set schema constraints ──────────────────────────────────────────────


class TestCreateGeneSetRequestConstraints:
    def test_name_max_length(self) -> None:
        CreateGeneSetRequest(name="a" * 200, siteId="x", geneIds=["G1"])
        with pytest.raises(ValidationError):
            CreateGeneSetRequest(name="a" * 201, siteId="x", geneIds=["G1"])

    def test_invalid_source_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CreateGeneSetRequest(
                name="X",
                siteId="x",
                geneIds=["G1"],
                source="invalid",  # type: ignore[arg-type]
            )


class TestSetOperationRequestConstraints:
    def test_name_max_length(self) -> None:
        SetOperationRequest(setAId="a", setBId="b", operation="union", name="x" * 200)
        with pytest.raises(ValidationError):
            SetOperationRequest(
                setAId="a", setBId="b", operation="union", name="x" * 201
            )


# ── SSE helpers (custom code) ────────────────────────────────────────────────


class TestSSEHeaders:
    def test_required_headers(self) -> None:
        assert SSE_HEADERS["Cache-Control"] == "no-cache"
        assert SSE_HEADERS["Connection"] == "keep-alive"
        assert SSE_HEADERS["X-Accel-Buffering"] == "no"


class TestSSEStream:
    async def test_basic_stream(self) -> None:
        async def producer(send):
            await send({"type": "progress", "data": {"percent": 50}})
            await send({"type": "done", "data": {"result": "ok"}})

        frames = [frame async for frame in sse_stream(producer, {"done"})]
        assert len(frames) == 2
        assert frames[0] == f"event: progress\ndata: {json.dumps({'percent': 50})}\n\n"
        assert frames[1] == f"event: done\ndata: {json.dumps({'result': 'ok'})}\n\n"

    async def test_terminates_on_end_event(self) -> None:
        async def producer(send):
            await send({"type": "progress", "data": {}})
            await send({"type": "error", "data": {"msg": "fail"}})
            await send({"type": "progress", "data": {"extra": True}})

        frames = [frame async for frame in sse_stream(producer, {"done", "error"})]
        assert len(frames) == 2
        assert "error" in frames[1]

    async def test_default_event_type(self) -> None:
        async def producer(send):
            await send({"data": {"x": 1}})
            await send({"type": "done", "data": {}})

        frames = [frame async for frame in sse_stream(producer, {"done"})]
        assert len(frames) == 2
        assert frames[0].startswith("event: experiment_progress")

    async def test_default_data(self) -> None:
        async def producer(send):
            await send({"type": "done"})

        frames = [frame async for frame in sse_stream(producer, {"done"})]
        assert len(frames) == 1
        assert "data: {}" in frames[0]

    async def test_multiple_end_event_types(self) -> None:
        async def producer(send):
            await send({"type": "completed", "data": {}})

        frames = [
            frame
            async for frame in sse_stream(producer, {"completed", "error", "cancelled"})
        ]
        assert len(frames) == 1
        assert "completed" in frames[0]
