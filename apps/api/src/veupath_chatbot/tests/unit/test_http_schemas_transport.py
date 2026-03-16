"""Comprehensive tests for transport/http schema validation and serialization.

Covers all Pydantic models in the schemas/ package: construction, alias
handling (populate_by_name + by_alias serialization), defaults, required
fields, validators, bounds constraints, and extra-field behavior.
"""

import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from veupath_chatbot.transport.http.schemas.chat import (
    ChatMention,
    ChatRequest,
    MessageResponse,
    SubKaniActivityResponse,
    ThinkingResponse,
    ToolCallResponse,
)
from veupath_chatbot.transport.http.schemas.experiments import (
    AiAssistRequest,
    BatchOrganismTargetRequest,
    BenchmarkControlSet,
    CreateBatchExperimentRequest,
    CreateBenchmarkRequest,
    CreateExperimentRequest,
    CustomEnrichRequest,
    EnrichmentCompareRequest,
    OperatorKnobRequest,
    OptimizationSpecRequest,
    OverlapRequest,
    RefineRequest,
    RunAnalysisRequest,
    RunCrossValidationRequest,
    RunEnrichmentRequest,
    ThresholdKnobRequest,
    ThresholdSweepRequest,
)
from veupath_chatbot.transport.http.schemas.gene_sets import (
    CreateGeneSetRequest,
    GeneSetEnrichRequest,
    GeneSetResponse,
    RunGeneSetAnalysisRequest,
    SetOperationRequest,
)
from veupath_chatbot.transport.http.schemas.health import HealthResponse
from veupath_chatbot.transport.http.schemas.plan import (
    BasePlanNode,
    ColocationParams,
    PlanMetadata,
    PlanNode,
    PlanNormalizeRequest,
    PlanNormalizeResponse,
    StepAnalysisSpec,
    StepFilterSpec,
    StepReportSpec,
    StrategyPlan,
)
from veupath_chatbot.transport.http.schemas.sites import (
    DependentParamsRequest,
    DependentParamsResponse,
    ParamSpecResponse,
    ParamSpecsRequest,
    RecordTypeResponse,
    SearchDetailsResponse,
    SearchResponse,
    SearchValidationErrors,
    SearchValidationPayload,
    SearchValidationRequest,
    SearchValidationResponse,
    SiteResponse,
)
from veupath_chatbot.transport.http.schemas.steps import (
    StepAnalysisRequest,
    StepAnalysisResponse,
    StepAnalysisRunResponse,
    StepFilterRequest,
    StepFilterResponse,
    StepFiltersResponse,
    StepReportRequest,
    StepReportResponse,
    StepReportRunResponse,
    StepResponse,
)
from veupath_chatbot.transport.http.schemas.strategies import (
    CreateStrategyRequest,
    OpenStrategyRequest,
    OpenStrategyResponse,
    StepCountsRequest,
    StepCountsResponse,
    StrategyResponse,
    UpdateStrategyRequest,
    WdkStrategySummaryResponse,
)
from veupath_chatbot.transport.http.schemas.veupathdb_auth import (
    AuthStatusResponse,
    AuthSuccessResponse,
)
from veupath_chatbot.transport.http.sse import SSE_HEADERS, sse_stream

# ── Chat schemas ─────────────────────────────────────────────────────────────


class TestToolCallResponse:
    def test_construction(self) -> None:
        tc = ToolCallResponse(id="t1", name="search", arguments={"q": "gene"})
        assert tc.id == "t1"
        assert tc.name == "search"
        assert tc.arguments == {"q": "gene"}
        assert tc.result is None

    def test_with_result(self) -> None:
        tc = ToolCallResponse(id="t1", name="run", arguments={}, result="done")
        assert tc.result == "done"

    def test_missing_required_fields(self) -> None:
        with pytest.raises(ValidationError):
            ToolCallResponse(id="t1", name="x")  # type: ignore[call-arg]


class TestChatMention:
    def test_construction_with_alias(self) -> None:
        m = ChatMention(type="strategy", id="s1", displayName="My Strat")
        assert m.display_name == "My Strat"

    def test_construction_with_python_name(self) -> None:
        m = ChatMention(type="strategy", id="s1", display_name="My Strat")
        assert m.display_name == "My Strat"

    def test_serialization_by_alias(self) -> None:
        m = ChatMention(type="experiment", id="e1", displayName="Exp 1")
        data = m.model_dump(by_alias=True)
        assert "displayName" in data
        assert data["displayName"] == "Exp 1"

    def test_invalid_type(self) -> None:
        with pytest.raises(ValidationError):
            ChatMention(type="invalid", id="x", displayName="X")  # type: ignore[arg-type]


class TestChatRequest:
    def test_valid_minimal(self) -> None:
        req = ChatRequest(siteId="plasmodb", message="hello")
        assert req.site_id == "plasmodb"
        assert req.strategy_id is None

    def test_serialization_by_alias(self) -> None:
        req = ChatRequest(siteId="plasmodb", message="hello")
        data = req.model_dump(by_alias=True)
        assert "siteId" in data
        assert "strategyId" in data
        assert "reasoningEffort" in data

    def test_message_max_length(self) -> None:
        # At the boundary
        req = ChatRequest(siteId="x", message="a" * 200_000)
        assert len(req.message) == 200_000
        # Over the boundary
        with pytest.raises(ValidationError):
            ChatRequest(siteId="x", message="a" * 200_001)

    def test_provider_validation(self) -> None:
        req = ChatRequest(siteId="x", message="hi", provider="anthropic")
        assert req.provider == "anthropic"
        with pytest.raises(ValidationError):
            ChatRequest(siteId="x", message="hi", provider="invalid_provider")  # type: ignore[arg-type]

    def test_reasoning_effort_validation(self) -> None:
        req = ChatRequest(siteId="x", message="hi", reasoningEffort="high")
        assert req.reasoning_effort == "high"
        with pytest.raises(ValidationError):
            ChatRequest(siteId="x", message="hi", reasoningEffort="ultra")  # type: ignore[arg-type]

    def test_with_strategy_id(self) -> None:
        sid = uuid4()
        req = ChatRequest(siteId="x", message="hi", strategyId=sid)
        assert req.strategy_id == sid

    def test_with_model_override(self) -> None:
        req = ChatRequest(siteId="x", message="hi", model="gpt-4")
        assert req.model_id == "gpt-4"


class TestSubKaniActivityResponse:
    def test_construction(self) -> None:
        tc = ToolCallResponse(id="t1", name="tool", arguments={})
        resp = SubKaniActivityResponse(
            calls={"agent1": [tc]},
            status={"agent1": "done"},
        )
        assert "agent1" in resp.calls
        assert resp.status["agent1"] == "done"


class TestThinkingResponse:
    def test_defaults_all_none(self) -> None:
        t = ThinkingResponse()
        assert t.tool_calls is None
        assert t.last_tool_calls is None
        assert t.sub_kani_calls is None
        assert t.sub_kani_status is None
        assert t.reasoning is None
        assert t.updated_at is None

    def test_with_values(self) -> None:
        now = datetime.now(UTC)
        tc = ToolCallResponse(id="t1", name="search", arguments={})
        t = ThinkingResponse(
            toolCalls=[tc],
            lastToolCalls=[tc],
            subKaniCalls={"sub": [tc]},
            subKaniStatus={"sub": "running"},
            reasoning="thinking...",
            updatedAt=now,
        )
        assert t.tool_calls is not None and len(t.tool_calls) == 1
        assert t.last_tool_calls is not None
        assert t.sub_kani_calls is not None
        assert t.updated_at == now

    def test_serialization_by_alias(self) -> None:
        t = ThinkingResponse(reasoning="test")
        data = t.model_dump(by_alias=True)
        assert "toolCalls" in data
        assert "lastToolCalls" in data
        assert "subKaniCalls" in data
        assert "subKaniStatus" in data
        assert "updatedAt" in data


class TestMessageResponse:
    def test_required_fields(self) -> None:
        with pytest.raises(ValidationError):
            MessageResponse(role="user", content="hi")  # type: ignore[call-arg]
        # timestamp is required

    def test_extra_fields_ignored(self) -> None:
        """model_config has extra='ignore' -- unknown fields should be silently dropped."""
        now = datetime.now(UTC)
        msg = MessageResponse.model_validate(
            {
                "role": "user",
                "content": "hi",
                "timestamp": now.isoformat(),
                "bogus": 123,
            }
        )
        assert msg.role == "user"
        assert not hasattr(msg, "bogus")

    def test_serialization_by_alias(self) -> None:
        now = datetime.now(UTC)
        msg = MessageResponse(role="assistant", content="ok", timestamp=now)
        data = msg.model_dump(by_alias=True)
        assert "toolCalls" in data
        assert "subKaniActivity" in data
        assert "planningArtifacts" in data
        assert "optimizationProgress" in data

    def test_with_sub_kani_activity(self) -> None:
        now = datetime.now(UTC)
        tc = ToolCallResponse(id="t1", name="tool", arguments={})
        activity = SubKaniActivityResponse(calls={"a": [tc]}, status={"a": "done"})
        msg = MessageResponse(
            role="assistant", content="ok", timestamp=now, subKaniActivity=activity
        )
        assert msg.sub_kani_activity is not None
        assert "a" in msg.sub_kani_activity.calls


# ── Health schemas ───────────────────────────────────────────────────────────


class TestHealthResponse:
    def test_construction(self) -> None:
        now = datetime.now(UTC)
        h = HealthResponse(status="healthy", version="1.0.0", timestamp=now)
        assert h.status == "healthy"
        assert h.version == "1.0.0"
        assert h.timestamp == now

    def test_missing_fields(self) -> None:
        with pytest.raises(ValidationError):
            HealthResponse(status="healthy")  # type: ignore[call-arg]

    def test_serialization(self) -> None:
        now = datetime.now(UTC)
        h = HealthResponse(status="ok", version="2", timestamp=now)
        data = h.model_dump()
        assert data["status"] == "ok"
        assert "timestamp" in data


# ── VEuPathDB auth schemas ──────────────────────────────────────────────────


class TestAuthSuccessResponse:
    def test_construction(self) -> None:
        r = AuthSuccessResponse(success=True)
        assert r.success is True

    def test_missing_success(self) -> None:
        with pytest.raises(ValidationError):
            AuthSuccessResponse()  # type: ignore[call-arg]


class TestAuthStatusResponse:
    def test_signed_in(self) -> None:
        r = AuthStatusResponse(signedIn=True, name="User", email="u@example.com")
        assert r.signedIn is True
        assert r.name == "User"
        assert r.email == "u@example.com"

    def test_signed_out_defaults(self) -> None:
        r = AuthStatusResponse(signedIn=False)
        assert r.name is None
        assert r.email is None


# ── Sites schemas ────────────────────────────────────────────────────────────


class TestSiteResponse:
    def test_alias_construction(self) -> None:
        s = SiteResponse(
            id="plasmodb",
            name="PlasmoDB",
            displayName="PlasmoDB",
            baseUrl="https://plasmodb.org",
            projectId="PlasmoDB",
            isPortal=False,
        )
        assert s.display_name == "PlasmoDB"
        assert s.base_url == "https://plasmodb.org"
        assert s.project_id == "PlasmoDB"
        assert s.is_portal is False

    def test_python_name_construction(self) -> None:
        s = SiteResponse(
            id="toxodb",
            name="ToxoDB",
            display_name="ToxoDB",
            base_url="https://toxodb.org",
            project_id="ToxoDB",
            is_portal=False,
        )
        assert s.display_name == "ToxoDB"

    def test_serialization_by_alias(self) -> None:
        s = SiteResponse(
            id="x",
            name="X",
            displayName="X",
            baseUrl="http://x",
            projectId="X",
            isPortal=True,
        )
        data = s.model_dump(by_alias=True)
        assert "displayName" in data
        assert "baseUrl" in data
        assert "projectId" in data
        assert "isPortal" in data

    def test_missing_required(self) -> None:
        with pytest.raises(ValidationError):
            SiteResponse(id="x", name="X")  # type: ignore[call-arg]


class TestRecordTypeResponse:
    def test_construction(self) -> None:
        r = RecordTypeResponse(name="gene", displayName="Gene")
        assert r.display_name == "Gene"
        assert r.description is None

    def test_with_description(self) -> None:
        r = RecordTypeResponse(name="gene", displayName="Gene", description="A gene")
        assert r.description == "A gene"


class TestSearchResponse:
    def test_construction(self) -> None:
        s = SearchResponse(
            name="GenesByOrganism", displayName="Genes by Organism", recordType="gene"
        )
        assert s.display_name == "Genes by Organism"
        assert s.record_type == "gene"
        assert s.description is None


class TestDependentParamsRequest:
    def test_defaults(self) -> None:
        r = DependentParamsRequest(parameterName="org")
        assert r.parameter_name == "org"
        assert r.context_values == {}

    def test_with_context(self) -> None:
        r = DependentParamsRequest(
            parameterName="org",
            contextValues={"species": "falciparum"},
        )
        assert r.context_values == {"species": "falciparum"}


class TestSearchDetailsResponse:
    def test_defaults(self) -> None:
        r = SearchDetailsResponse()
        assert r.search_data is None
        assert r.validation is None
        assert r.parameters is None

    def test_extra_fields_allowed(self) -> None:
        """SearchDetailsResponse has extra='allow'."""
        r = SearchDetailsResponse.model_validate({"custom_field": "value"})
        assert r.model_extra is not None
        assert r.model_extra.get("custom_field") == "value"


class TestDependentParamsResponse:
    def test_root_model(self) -> None:
        r = DependentParamsResponse([{"name": "param1", "value": "val1"}])
        assert r.root == [{"name": "param1", "value": "val1"}]

    def test_empty_array(self) -> None:
        r = DependentParamsResponse([])
        assert r.root == []


class TestSearchValidationRequest:
    def test_defaults(self) -> None:
        r = SearchValidationRequest()
        assert r.context_values == {}

    def test_with_values(self) -> None:
        r = SearchValidationRequest(contextValues={"organism": "P. falciparum"})
        assert r.context_values["organism"] == "P. falciparum"


class TestParamSpecsRequest:
    def test_defaults(self) -> None:
        r = ParamSpecsRequest()
        assert r.context_values == {}


class TestSearchValidationErrors:
    def test_defaults(self) -> None:
        e = SearchValidationErrors()
        assert e.general == []
        assert e.by_key == {}

    def test_with_errors(self) -> None:
        e = SearchValidationErrors(
            general=["Something wrong"],
            byKey={"organism": ["Required"]},
        )
        assert len(e.general) == 1
        assert "organism" in e.by_key


class TestSearchValidationPayload:
    def test_valid(self) -> None:
        p = SearchValidationPayload(isValid=True)
        assert p.is_valid is True
        assert p.normalized_context_values == {}
        assert p.errors.general == []

    def test_invalid_with_errors(self) -> None:
        errs = SearchValidationErrors(general=["Bad"], byKey={"p": ["missing"]})
        p = SearchValidationPayload(
            isValid=False,
            normalizedContextValues={"p": "default"},
            errors=errs,
        )
        assert not p.is_valid
        assert p.errors.by_key["p"] == ["missing"]


class TestSearchValidationResponse:
    def test_wraps_payload(self) -> None:
        payload = SearchValidationPayload(isValid=True)
        r = SearchValidationResponse(validation=payload)
        assert r.validation.is_valid is True


class TestParamSpecResponse:
    def test_minimal(self) -> None:
        p = ParamSpecResponse(name="org", type="string")
        assert p.name == "org"
        assert p.display_name is None
        assert p.allow_empty_value is False
        assert p.is_number is False
        assert p.count_only_leaves is False

    def test_full(self) -> None:
        p = ParamSpecResponse(
            name="score",
            displayName="Score",
            type="number",
            allowEmptyValue=True,
            allowMultipleValues=False,
            multiPick=False,
            minSelectedCount=1,
            maxSelectedCount=10,
            countOnlyLeaves=True,
            initialDisplayValue="0.5",
            vocabulary=["a", "b"],
            min=0.0,
            max=1.0,
            isNumber=True,
            increment=0.1,
        )
        assert p.display_name == "Score"
        assert p.allow_empty_value is True
        assert p.min_value == 0.0
        assert p.max_value == 1.0
        assert p.is_number is True

    def test_serialization_by_alias(self) -> None:
        p = ParamSpecResponse(name="x", type="str", isNumber=True, min=0, max=10)
        data = p.model_dump(by_alias=True)
        assert "displayName" in data
        assert "allowEmptyValue" in data
        assert "isNumber" in data
        # Field aliases "min" and "max" for min_value/max_value
        assert "min" in data
        assert "max" in data


# ── Steps schemas ────────────────────────────────────────────────────────────


class TestStepFilterResponse:
    def test_construction(self) -> None:
        f = StepFilterResponse(name="organism", value="P. falciparum")
        assert f.name == "organism"
        assert f.disabled is False

    def test_disabled(self) -> None:
        f = StepFilterResponse(name="score", value=0.5, disabled=True)
        assert f.disabled is True


class TestStepFiltersResponse:
    def test_list_of_filters(self) -> None:
        f1 = StepFilterResponse(name="a", value=1)
        f2 = StepFilterResponse(name="b", value="x")
        resp = StepFiltersResponse(filters=[f1, f2])
        assert len(resp.filters) == 2


class TestStepAnalysisResponse:
    def test_alias(self) -> None:
        a = StepAnalysisResponse(analysisType="go_enrichment")
        assert a.analysis_type == "go_enrichment"
        assert a.parameters == {}
        assert a.custom_name is None

    def test_with_custom_name(self) -> None:
        a = StepAnalysisResponse(
            analysisType="pathway", parameters={"k": "v"}, customName="My Analysis"
        )
        assert a.custom_name == "My Analysis"


class TestStepReportResponse:
    def test_defaults(self) -> None:
        r = StepReportResponse()
        assert r.report_name == "standard"
        assert r.config == {}

    def test_custom(self) -> None:
        r = StepReportResponse(reportName="tabular", config={"cols": ["a"]})
        assert r.report_name == "tabular"


class TestStepAnalysisRunResponse:
    def test_construction(self) -> None:
        a = StepAnalysisResponse(analysisType="go")
        run = StepAnalysisRunResponse(analysis=a, wdk={"result": "data"})
        assert run.analysis.analysis_type == "go"
        assert run.wdk is not None

    def test_wdk_optional(self) -> None:
        a = StepAnalysisResponse(analysisType="go")
        run = StepAnalysisRunResponse(analysis=a)
        assert run.wdk is None


class TestStepReportRunResponse:
    def test_construction(self) -> None:
        r = StepReportResponse(reportName="tabular")
        run = StepReportRunResponse(report=r, wdk={"data": []})
        assert run.report.report_name == "tabular"

    def test_wdk_optional(self) -> None:
        run = StepReportRunResponse(report=StepReportResponse())
        assert run.wdk is None


class TestStepResponse:
    def test_minimal(self) -> None:
        s = StepResponse(id="s1", displayName="Step 1")
        assert s.id == "s1"
        assert s.display_name == "Step 1"
        assert s.kind is None
        assert s.search_name is None
        assert s.result_count is None

    def test_full(self) -> None:
        f = StepFilterResponse(name="f1", value="v1")
        a = StepAnalysisResponse(analysisType="go")
        r = StepReportResponse(reportName="tab")
        s = StepResponse(
            id="s2",
            kind="search",
            displayName="Search Step",
            searchName="GenesByOrganism",
            recordType="gene",
            parameters={"org": "Pf"},
            operator="INTERSECT",
            colocationParams={"upstream": 100, "downstream": 50},
            primaryInputStepId="s1",
            secondaryInputStepId="s0",
            resultCount=42,
            wdkStepId=999,
            filters=[f],
            analyses=[a],
            reports=[r],
        )
        assert s.result_count == 42
        assert s.wdk_step_id == 999
        assert s.primary_input_step_id == "s1"
        assert s.secondary_input_step_id == "s0"
        assert s.filters is not None and len(s.filters) == 1
        assert s.analyses is not None and len(s.analyses) == 1
        assert s.reports is not None and len(s.reports) == 1

    def test_serialization_by_alias(self) -> None:
        s = StepResponse(id="s1", displayName="S", resultCount=10, wdkStepId=1)
        data = s.model_dump(by_alias=True)
        assert "displayName" in data
        assert "resultCount" in data
        assert "wdkStepId" in data
        assert "primaryInputStepId" in data
        assert "secondaryInputStepId" in data
        assert "colocationParams" in data
        assert "searchName" in data
        assert "recordType" in data


class TestStepFilterRequest:
    def test_construction(self) -> None:
        r = StepFilterRequest(value="abc")
        assert r.value == "abc"
        assert r.disabled is False

    def test_disabled(self) -> None:
        r = StepFilterRequest(value=42, disabled=True)
        assert r.disabled is True


class TestStepAnalysisRequest:
    def test_alias(self) -> None:
        r = StepAnalysisRequest(analysisType="go_enrichment")
        assert r.analysis_type == "go_enrichment"
        assert r.parameters == {}
        assert r.custom_name is None


class TestStepReportRequest:
    def test_defaults(self) -> None:
        r = StepReportRequest()
        assert r.report_name == "standard"
        assert r.config == {}

    def test_custom(self) -> None:
        r = StepReportRequest(reportName="tabular", config={"cols": ["id"]})
        assert r.report_name == "tabular"


# ── Plan schemas ─────────────────────────────────────────────────────────────


class TestPlanMetadata:
    def test_defaults(self) -> None:
        m = PlanMetadata()
        assert m.name is None
        assert m.description is None
        assert m.siteId is None
        assert m.createdAt is None

    def test_with_values(self) -> None:
        m = PlanMetadata(name="My Plan", siteId="plasmodb")
        assert m.name == "My Plan"


class TestStepFilterSpec:
    def test_construction(self) -> None:
        f = StepFilterSpec(name="organism", value="Pf")
        assert f.name == "organism"
        assert f.disabled is False

    def test_disabled(self) -> None:
        f = StepFilterSpec(name="score", value=0.5, disabled=True)
        assert f.disabled is True


class TestStepAnalysisSpec:
    def test_defaults(self) -> None:
        a = StepAnalysisSpec(analysisType="go_enrichment")
        assert a.parameters == {}
        assert a.customName is None


class TestStepReportSpec:
    def test_defaults(self) -> None:
        r = StepReportSpec()
        assert r.reportName == "standard"
        assert r.config == {}


class TestColocationParams:
    def test_construction(self) -> None:
        c = ColocationParams(upstream=100, downstream=200)
        assert c.upstream == 100
        assert c.downstream == 200
        assert c.strand == "both"

    def test_negative_upstream_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ColocationParams(upstream=-1, downstream=0)

    def test_negative_downstream_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ColocationParams(upstream=0, downstream=-1)


class TestBasePlanNode:
    def test_defaults(self) -> None:
        n = BasePlanNode()
        assert n.id is None
        assert n.displayName is None
        assert n.filters is None
        assert n.analyses is None
        assert n.reports is None

    def test_extra_fields_allowed(self) -> None:
        """BasePlanNode has extra='allow' for WDK-originated keys."""
        n = BasePlanNode.model_validate({"wdkStepId": 42, "estimatedSize": 100})
        assert n.model_extra is not None
        assert n.model_extra.get("wdkStepId") == 42


class TestPlanNode:
    def test_simple_search_node(self) -> None:
        n = PlanNode(searchName="GenesByOrganism")
        assert n.searchName == "GenesByOrganism"
        assert n.parameters == {}
        assert n.primaryInput is None
        assert n.secondaryInput is None
        assert n.operator is None
        assert n.colocationParams is None

    def test_transform_node(self) -> None:
        """Transform: has primaryInput but no secondaryInput."""
        leaf = PlanNode(searchName="GenesByOrganism")
        transform = PlanNode(searchName="GenesByTransform", primaryInput=leaf)
        assert transform.primaryInput is not None
        assert transform.secondaryInput is None

    def test_combine_node(self) -> None:
        leaf1 = PlanNode(searchName="GenesByOrganism")
        leaf2 = PlanNode(searchName="GenesByProduct")
        combine = PlanNode(
            searchName="GenesByOrganism",
            primaryInput=leaf1,
            secondaryInput=leaf2,
            operator="UNION",
        )
        assert combine.operator == "UNION"
        assert combine.secondaryInput is not None

    def test_secondary_without_primary_rejected(self) -> None:
        """secondaryInput requires primaryInput."""
        leaf = PlanNode(searchName="GenesByOrganism")
        with pytest.raises(
            ValidationError, match="secondaryInput requires primaryInput"
        ):
            PlanNode(searchName="X", secondaryInput=leaf)

    def test_secondary_without_operator_rejected(self) -> None:
        """operator is required when secondaryInput is present."""
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
        assert n.colocationParams.upstream == 500

    def test_extra_fields_allowed(self) -> None:
        n = PlanNode.model_validate(
            {"searchName": "X", "wdkStepId": 123, "estimatedSize": 500}
        )
        assert n.model_extra is not None
        assert n.model_extra.get("wdkStepId") == 123

    def test_deeply_nested_tree(self) -> None:
        """Test 3-level nesting."""
        l1 = PlanNode(searchName="Leaf1")
        l2 = PlanNode(searchName="Leaf2")
        l3 = PlanNode(searchName="Leaf3")
        combine1 = PlanNode(
            searchName="Combine1",
            primaryInput=l1,
            secondaryInput=l2,
            operator="INTERSECT",
        )
        combine2 = PlanNode(
            searchName="Combine2",
            primaryInput=combine1,
            secondaryInput=l3,
            operator="UNION",
        )
        assert combine2.primaryInput is not None
        assert combine2.primaryInput.secondaryInput is not None


class TestStrategyPlan:
    def test_basic(self) -> None:
        root = PlanNode(searchName="GenesByOrganism")
        plan = StrategyPlan(recordType="gene", root=root)
        assert plan.recordType == "gene"
        assert plan.metadata is None

    def test_with_metadata(self) -> None:
        root = PlanNode(searchName="X")
        meta = PlanMetadata(name="Test", siteId="plasmodb")
        plan = StrategyPlan(recordType="gene", root=root, metadata=meta)
        assert plan.metadata is not None
        assert plan.metadata.name == "Test"

    def test_extra_fields_allowed(self) -> None:
        plan = StrategyPlan.model_validate(
            {"recordType": "gene", "root": {"searchName": "X"}, "customField": "yes"}
        )
        assert plan.model_extra is not None
        assert plan.model_extra.get("customField") == "yes"


class TestPlanNormalizeRequest:
    def test_construction(self) -> None:
        root = PlanNode(searchName="X")
        plan = StrategyPlan(recordType="gene", root=root)
        req = PlanNormalizeRequest(siteId="plasmodb", plan=plan)
        assert req.siteId == "plasmodb"


class TestPlanNormalizeResponse:
    def test_no_warnings(self) -> None:
        root = PlanNode(searchName="X")
        plan = StrategyPlan(recordType="gene", root=root)
        resp = PlanNormalizeResponse(plan=plan)
        assert resp.warnings is None

    def test_with_warnings(self) -> None:
        root = PlanNode(searchName="X")
        plan = StrategyPlan(recordType="gene", root=root)
        resp = PlanNormalizeResponse(plan=plan, warnings=["param X normalized"])
        assert resp.warnings is not None and len(resp.warnings) == 1


# ── Strategy schemas ─────────────────────────────────────────────────────────


class TestStepCountsRequest:
    def test_construction(self) -> None:
        root = PlanNode(searchName="X")
        plan = StrategyPlan(recordType="gene", root=root)
        req = StepCountsRequest(siteId="plasmodb", plan=plan)
        assert req.site_id == "plasmodb"


class TestStepCountsResponse:
    def test_construction(self) -> None:
        resp = StepCountsResponse(counts={"step1": 42, "step2": None})
        assert resp.counts["step1"] == 42
        assert resp.counts["step2"] is None


class TestWdkStrategySummaryResponse:
    def test_construction(self) -> None:
        r = WdkStrategySummaryResponse(
            wdkStrategyId=123, name="My Strategy", siteId="plasmodb"
        )
        assert r.wdk_strategy_id == 123
        assert r.name == "My Strategy"
        assert r.wdk_url is None
        assert r.is_internal is False

    def test_serialization(self) -> None:
        r = WdkStrategySummaryResponse(
            wdkStrategyId=1, name="S", siteId="x", wdkUrl="http://x", isSaved=True
        )
        data = r.model_dump(by_alias=True)
        assert "wdkStrategyId" in data
        assert "siteId" in data
        assert "wdkUrl" in data
        assert "isSaved" in data
        assert "isInternal" in data


class TestOpenStrategyRequest:
    def test_all_optional(self) -> None:
        req = OpenStrategyRequest()
        assert req.strategy_id is None
        assert req.wdk_strategy_id is None
        assert req.site_id is None

    def test_with_strategy_id(self) -> None:
        sid = uuid4()
        req = OpenStrategyRequest(strategyId=sid, siteId="plasmodb")
        assert req.strategy_id == sid
        assert req.site_id == "plasmodb"

    def test_with_wdk_strategy_id(self) -> None:
        req = OpenStrategyRequest(wdkStrategyId=42, siteId="plasmodb")
        assert req.wdk_strategy_id == 42


class TestOpenStrategyResponse:
    def test_construction(self) -> None:
        sid = uuid4()
        resp = OpenStrategyResponse(strategyId=sid)
        assert resp.strategy_id == sid

    def test_serialization(self) -> None:
        sid = uuid4()
        resp = OpenStrategyResponse(strategyId=sid)
        data = resp.model_dump(by_alias=True)
        assert "strategyId" in data
        assert data["strategyId"] == sid


class TestStrategyResponse:
    def test_list_view_defaults(self) -> None:
        now = datetime.now(UTC)
        sid = uuid4()
        resp = StrategyResponse(
            id=sid,
            name="Test",
            siteId="plasmodb",
            recordType="gene",
            createdAt=now,
            updatedAt=now,
        )
        assert resp.steps == []
        assert resp.is_saved is False
        assert resp.messages is None
        assert resp.thinking is None
        assert resp.wdk_strategy_id is None
        assert resp.step_count is None
        assert resp.result_count is None
        assert resp.wdk_url is None
        assert resp.root_step_id is None
        assert resp.model_id is None

    def test_detail_view(self) -> None:
        now = datetime.now(UTC)
        sid = uuid4()
        step = StepResponse(id="s1", displayName="Step 1")
        resp = StrategyResponse(
            id=sid,
            name="Test",
            siteId="plasmodb",
            recordType="gene",
            createdAt=now,
            updatedAt=now,
            steps=[step],
            rootStepId="s1",
            wdkStrategyId=100,
            isSaved=True,
            stepCount=1,
            resultCount=42,
        )
        assert len(resp.steps) == 1
        assert resp.root_step_id == "s1"
        assert resp.wdk_strategy_id == 100
        assert resp.is_saved is True
        assert resp.step_count == 1

    def test_serialization_by_alias(self) -> None:
        now = datetime.now(UTC)
        resp = StrategyResponse(
            id=uuid4(),
            name="X",
            siteId="x",
            recordType="gene",
            createdAt=now,
            updatedAt=now,
        )
        data = resp.model_dump(by_alias=True)
        assert "siteId" in data
        assert "recordType" in data
        assert "rootStepId" in data
        assert "wdkStrategyId" in data
        assert "isSaved" in data
        assert "createdAt" in data
        assert "updatedAt" in data
        assert "stepCount" in data
        assert "resultCount" in data
        assert "wdkUrl" in data
        assert "modelId" in data


class TestCreateStrategyRequest:
    def test_valid(self) -> None:
        plan = StrategyPlan(recordType="gene", root=PlanNode(searchName="X"))
        req = CreateStrategyRequest(name="My Strat", siteId="plasmodb", plan=plan)
        assert req.name == "My Strat"

    def test_name_min_length(self) -> None:
        plan = StrategyPlan(recordType="gene", root=PlanNode(searchName="X"))
        with pytest.raises(ValidationError):
            CreateStrategyRequest(name="", siteId="plasmodb", plan=plan)

    def test_name_max_length(self) -> None:
        plan = StrategyPlan(recordType="gene", root=PlanNode(searchName="X"))
        with pytest.raises(ValidationError):
            CreateStrategyRequest(name="a" * 256, siteId="plasmodb", plan=plan)

    def test_name_at_max_length(self) -> None:
        plan = StrategyPlan(recordType="gene", root=PlanNode(searchName="X"))
        req = CreateStrategyRequest(name="a" * 255, siteId="plasmodb", plan=plan)
        assert len(req.name) == 255


class TestUpdateStrategyRequest:
    def test_all_optional(self) -> None:
        req = UpdateStrategyRequest()
        assert req.name is None
        assert req.plan is None
        assert req.wdk_strategy_id is None
        assert req.is_saved is None

    def test_partial_update(self) -> None:
        req = UpdateStrategyRequest(name="New Name", isSaved=True)
        assert req.name == "New Name"
        assert req.is_saved is True
        assert req.plan is None

    def test_name_empty_rejected(self) -> None:
        with pytest.raises(ValidationError):
            UpdateStrategyRequest(name="")

    def test_name_too_long_rejected(self) -> None:
        with pytest.raises(ValidationError):
            UpdateStrategyRequest(name="x" * 256)


# ── Experiment schemas ───────────────────────────────────────────────────────


class TestThresholdKnobRequest:
    def test_construction(self) -> None:
        k = ThresholdKnobRequest(stepId="s1", paramName="score")
        assert k.step_id == "s1"
        assert k.param_name == "score"
        assert k.min_val == 0
        assert k.max_val == 1
        assert k.step_size is None

    def test_custom_range(self) -> None:
        k = ThresholdKnobRequest(
            stepId="s1", paramName="p", minVal=0.1, maxVal=0.9, stepSize=0.05
        )
        assert k.min_val == 0.1
        assert k.max_val == 0.9
        assert k.step_size == 0.05

    def test_serialization(self) -> None:
        k = ThresholdKnobRequest(stepId="s1", paramName="p")
        data = k.model_dump(by_alias=True)
        assert "stepId" in data
        assert "paramName" in data
        assert "minVal" in data
        assert "maxVal" in data
        assert "stepSize" in data


class TestOperatorKnobRequest:
    def test_defaults(self) -> None:
        k = OperatorKnobRequest(combineNodeId="c1")
        assert k.combine_node_id == "c1"
        assert k.options == ["INTERSECT", "UNION", "MINUS"]

    def test_custom_options(self) -> None:
        k = OperatorKnobRequest(combineNodeId="c1", options=["INTERSECT", "UNION"])
        assert len(k.options) == 2


class TestOptimizationSpecRequest:
    def test_numeric(self) -> None:
        s = OptimizationSpecRequest(name="score", type="numeric", min=0.0, max=1.0)
        assert s.name == "score"
        assert s.type == "numeric"
        assert s.min == 0.0
        assert s.max == 1.0
        assert s.step is None
        assert s.choices is None

    def test_categorical(self) -> None:
        s = OptimizationSpecRequest(
            name="method", type="categorical", choices=["a", "b", "c"]
        )
        assert s.choices == ["a", "b", "c"]

    def test_integer(self) -> None:
        s = OptimizationSpecRequest(name="k", type="integer", min=1, max=10, step=1)
        assert s.type == "integer"
        assert s.step == 1

    def test_invalid_type(self) -> None:
        with pytest.raises(ValidationError):
            OptimizationSpecRequest(name="x", type="boolean")  # type: ignore[arg-type]


class TestCreateExperimentRequest:
    """Tests beyond what's in test_http_schemas_models.py."""

    def _base(self, **overrides: object) -> dict:
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

    def test_defaults(self) -> None:
        req = CreateExperimentRequest(**self._base())
        assert req.mode == "single"
        assert req.search_name == ""
        assert req.parameters == {}
        assert req.step_tree is None
        assert req.source_strategy_id is None
        assert req.optimization_target_step is None
        assert req.controls_value_format == "newline"
        assert req.enable_cross_validation is False
        assert req.k_folds == 5
        assert req.enrichment_types == []
        assert req.name == "Untitled Experiment"
        assert req.description == ""
        assert req.optimization_specs is None
        assert req.optimization_budget == 30
        assert req.optimization_objective is None
        assert req.parameter_display_values is None
        assert req.enable_step_analysis is False
        assert req.step_analysis_phases is None
        assert req.control_set_id is None
        assert req.threshold_knobs is None
        assert req.operator_knobs is None
        assert req.tree_optimization_objective == "precision_at_50"
        assert req.tree_optimization_budget == 50
        assert req.max_list_size is None
        assert req.sort_attribute is None
        assert req.sort_direction == "ASC"
        assert req.parent_experiment_id is None

    def test_optimization_budget_bounds(self) -> None:
        req = CreateExperimentRequest(**self._base(optimizationBudget=5))
        assert req.optimization_budget == 5
        req = CreateExperimentRequest(**self._base(optimizationBudget=200))
        assert req.optimization_budget == 200

        with pytest.raises(ValidationError):
            CreateExperimentRequest(**self._base(optimizationBudget=4))
        with pytest.raises(ValidationError):
            CreateExperimentRequest(**self._base(optimizationBudget=201))

    def test_tree_optimization_budget_bounds(self) -> None:
        req = CreateExperimentRequest(**self._base(treeOptimizationBudget=5))
        assert req.tree_optimization_budget == 5
        with pytest.raises(ValidationError):
            CreateExperimentRequest(**self._base(treeOptimizationBudget=4))
        with pytest.raises(ValidationError):
            CreateExperimentRequest(**self._base(treeOptimizationBudget=201))

    def test_name_max_length(self) -> None:
        req = CreateExperimentRequest(**self._base(name="a" * 200))
        assert len(req.name) == 200
        with pytest.raises(ValidationError):
            CreateExperimentRequest(**self._base(name="a" * 201))

    def test_description_max_length(self) -> None:
        req = CreateExperimentRequest(**self._base(description="x" * 2000))
        assert len(req.description) == 2000
        with pytest.raises(ValidationError):
            CreateExperimentRequest(**self._base(description="x" * 2001))

    def test_sort_direction_valid_values(self) -> None:
        req_asc = CreateExperimentRequest(**self._base(sortDirection="ASC"))
        assert req_asc.sort_direction == "ASC"
        req_desc = CreateExperimentRequest(**self._base(sortDirection="DESC"))
        assert req_desc.sort_direction == "DESC"
        with pytest.raises(ValidationError):
            CreateExperimentRequest(**self._base(sortDirection="RANDOM"))

    def test_controls_value_format_values(self) -> None:
        for fmt in ("newline", "json_list", "comma"):
            req = CreateExperimentRequest(**self._base(controlsValueFormat=fmt))
            assert req.controls_value_format == fmt
        with pytest.raises(ValidationError):
            CreateExperimentRequest(**self._base(controlsValueFormat="pipe"))

    def test_mode_values(self) -> None:
        for mode in ("single", "multi-step", "import"):
            req = CreateExperimentRequest(**self._base(mode=mode))
            assert req.mode == mode

    def test_enrichment_types(self) -> None:
        req = CreateExperimentRequest(
            **self._base(enrichmentTypes=["go_function", "pathway"])
        )
        assert req.enrichment_types == ["go_function", "pathway"]

    def test_optimization_objective_values(self) -> None:
        for obj in ("f1", "recall", "precision", "mcc"):
            req = CreateExperimentRequest(**self._base(optimizationObjective=obj))
            assert req.optimization_objective == obj
        with pytest.raises(ValidationError):
            CreateExperimentRequest(**self._base(optimizationObjective="invalid"))

    def test_serialization_by_alias(self) -> None:
        req = CreateExperimentRequest(**self._base())
        data = req.model_dump(by_alias=True)
        assert "siteId" in data
        assert "recordType" in data
        assert "positiveControls" in data
        assert "negativeControls" in data
        assert "controlsSearchName" in data
        assert "controlsParamName" in data
        assert "controlsValueFormat" in data
        assert "enableCrossValidation" in data
        assert "kFolds" in data
        assert "enrichmentTypes" in data
        assert "optimizationBudget" in data
        assert "treeOptimizationBudget" in data
        assert "treeOptimizationObjective" in data
        assert "sortDirection" in data
        assert "enableStepAnalysis" in data

    def test_missing_required_controls(self) -> None:
        with pytest.raises(ValidationError):
            CreateExperimentRequest(
                siteId="plasmodb",
                recordType="gene",
                controlsSearchName="X",
                controlsParamName="p",
                # missing positiveControls and negativeControls
            )


class TestBatchOrganismTargetRequest:
    def test_minimal(self) -> None:
        t = BatchOrganismTargetRequest(organism="Plasmodium falciparum")
        assert t.organism == "Plasmodium falciparum"
        assert t.positive_controls is None
        assert t.negative_controls is None

    def test_with_controls(self) -> None:
        t = BatchOrganismTargetRequest(
            organism="P. vivax",
            positiveControls=["G1"],
            negativeControls=["G2"],
        )
        assert t.positive_controls == ["G1"]
        assert t.negative_controls == ["G2"]


class TestCreateBatchExperimentRequest:
    def _base_experiment(self) -> CreateExperimentRequest:
        return CreateExperimentRequest(
            siteId="plasmodb",
            recordType="gene",
            positiveControls=["G1"],
            negativeControls=["G2"],
            controlsSearchName="GenesByLocusTag",
            controlsParamName="ds_gene_ids",
        )

    def test_valid(self) -> None:
        target = BatchOrganismTargetRequest(organism="P. falciparum")
        req = CreateBatchExperimentRequest(
            base=self._base_experiment(),
            organismParamName="organism",
            targetOrganisms=[target],
        )
        assert req.organism_param_name == "organism"
        assert len(req.target_organisms) == 1

    def test_empty_targets_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CreateBatchExperimentRequest(
                base=self._base_experiment(),
                organismParamName="organism",
                targetOrganisms=[],
            )


class TestRunCrossValidationRequest:
    def test_defaults(self) -> None:
        req = RunCrossValidationRequest()
        assert req.k_folds == 5

    def test_bounds(self) -> None:
        req = RunCrossValidationRequest(kFolds=2)
        assert req.k_folds == 2
        req = RunCrossValidationRequest(kFolds=10)
        assert req.k_folds == 10

        with pytest.raises(ValidationError):
            RunCrossValidationRequest(kFolds=1)
        with pytest.raises(ValidationError):
            RunCrossValidationRequest(kFolds=11)


class TestRunEnrichmentRequest:
    def test_valid(self) -> None:
        req = RunEnrichmentRequest(enrichmentTypes=["go_function", "pathway"])
        assert req.enrichment_types == ["go_function", "pathway"]

    def test_missing_required(self) -> None:
        with pytest.raises(ValidationError):
            RunEnrichmentRequest()  # type: ignore[call-arg]

    def test_invalid_type(self) -> None:
        with pytest.raises(ValidationError):
            RunEnrichmentRequest(enrichmentTypes=["invalid_type"])


class TestThresholdSweepRequest:
    def test_defaults(self) -> None:
        req = ThresholdSweepRequest(parameterName="score")
        assert req.parameter_name == "score"
        assert req.sweep_type == "numeric"
        assert req.min_value is None
        assert req.max_value is None
        assert req.steps == 10
        assert req.values is None

    def test_categorical(self) -> None:
        req = ThresholdSweepRequest(
            parameterName="method",
            sweepType="categorical",
            values=["a", "b", "c"],
        )
        assert req.sweep_type == "categorical"
        assert req.values == ["a", "b", "c"]

    def test_invalid_sweep_type(self) -> None:
        with pytest.raises(ValidationError):
            ThresholdSweepRequest(parameterName="x", sweepType="logarithmic")


class TestRunAnalysisRequest:
    def test_valid(self) -> None:
        req = RunAnalysisRequest(analysisName="go_enrichment", parameters={"k": "v"})
        assert req.analysis_name == "go_enrichment"
        assert req.parameters == {"k": "v"}

    def test_empty_name_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RunAnalysisRequest(analysisName="")

    def test_defaults(self) -> None:
        req = RunAnalysisRequest(analysisName="x")
        assert req.parameters == {}


class TestRefineRequest:
    def test_combine_defaults(self) -> None:
        req = RefineRequest(action="combine")
        assert req.action == "combine"
        assert req.search_name == ""
        assert req.parameters == {}
        assert req.operator == "INTERSECT"
        assert req.transform_name == ""

    def test_transform(self) -> None:
        req = RefineRequest(
            action="transform",
            searchName="GenesByTransform",
            transformName="MyTransform",
        )
        assert req.action == "transform"
        assert req.search_name == "GenesByTransform"
        assert req.transform_name == "MyTransform"

    def test_invalid_action(self) -> None:
        with pytest.raises(ValidationError):
            RefineRequest(action="delete")  # type: ignore[arg-type]


class TestCustomEnrichRequestExtended:
    def test_valid(self) -> None:
        req = CustomEnrichRequest(geneSetName="Kinases", geneIds=["G1", "G2"])
        assert req.gene_set_name == "Kinases"
        assert len(req.gene_ids) == 2

    def test_empty_name_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CustomEnrichRequest(geneSetName="", geneIds=["G1"])

    def test_empty_gene_ids_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CustomEnrichRequest(geneSetName="X", geneIds=[])


class TestBenchmarkControlSet:
    def test_valid(self) -> None:
        cs = BenchmarkControlSet(
            label="Set 1",
            positiveControls=["G1"],
            negativeControls=["G2"],
        )
        assert cs.label == "Set 1"
        assert cs.control_set_id is None
        assert cs.is_primary is False

    def test_empty_label_rejected(self) -> None:
        with pytest.raises(ValidationError):
            BenchmarkControlSet(
                label="", positiveControls=["G1"], negativeControls=["G2"]
            )

    def test_primary(self) -> None:
        cs = BenchmarkControlSet(
            label="Primary",
            positiveControls=["G1"],
            negativeControls=["G2"],
            isPrimary=True,
        )
        assert cs.is_primary is True


class TestCreateBenchmarkRequest:
    def test_valid(self) -> None:
        base = CreateExperimentRequest(
            siteId="plasmodb",
            recordType="gene",
            positiveControls=["G1"],
            negativeControls=["G2"],
            controlsSearchName="X",
            controlsParamName="p",
        )
        cs = BenchmarkControlSet(
            label="Set 1", positiveControls=["G1"], negativeControls=["G2"]
        )
        req = CreateBenchmarkRequest(base=base, controlSets=[cs])
        assert len(req.control_sets) == 1

    def test_empty_control_sets_rejected(self) -> None:
        base = CreateExperimentRequest(
            siteId="plasmodb",
            recordType="gene",
            positiveControls=["G1"],
            negativeControls=["G2"],
            controlsSearchName="X",
            controlsParamName="p",
        )
        with pytest.raises(ValidationError):
            CreateBenchmarkRequest(base=base, controlSets=[])


class TestOverlapRequestExtended:
    def test_valid(self) -> None:
        req = OverlapRequest(experimentIds=["e1", "e2", "e3"])
        assert len(req.experiment_ids) == 3

    def test_min_length(self) -> None:
        with pytest.raises(ValidationError):
            OverlapRequest(experimentIds=["e1"])

    def test_exactly_two(self) -> None:
        req = OverlapRequest(experimentIds=["e1", "e2"])
        assert len(req.experiment_ids) == 2


class TestEnrichmentCompareRequest:
    def test_valid(self) -> None:
        req = EnrichmentCompareRequest(experimentIds=["e1", "e2"])
        assert len(req.experiment_ids) == 2
        assert req.analysis_type is None

    def test_with_type(self) -> None:
        req = EnrichmentCompareRequest(
            experimentIds=["e1", "e2"], analysisType="go_function"
        )
        assert req.analysis_type == "go_function"

    def test_min_length(self) -> None:
        with pytest.raises(ValidationError):
            EnrichmentCompareRequest(experimentIds=["e1"])


class TestAiAssistRequest:
    def test_valid(self) -> None:
        req = AiAssistRequest(
            siteId="plasmodb", step="search", message="Help me find genes"
        )
        assert req.site_id == "plasmodb"
        assert req.step == "search"
        assert req.context == {}
        assert req.history == []
        assert req.model is None

    def test_all_wizard_steps(self) -> None:
        for ws in ("search", "parameters", "controls", "run", "results", "analysis"):
            req = AiAssistRequest(siteId="x", step=ws, message="hi")
            assert req.step == ws

    def test_invalid_step(self) -> None:
        with pytest.raises(ValidationError):
            AiAssistRequest(siteId="x", step="invalid", message="hi")  # type: ignore[arg-type]

    def test_empty_message_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AiAssistRequest(siteId="x", step="search", message="")

    def test_message_max_length(self) -> None:
        req = AiAssistRequest(siteId="x", step="search", message="a" * 50_000)
        assert len(req.message) == 50_000
        with pytest.raises(ValidationError):
            AiAssistRequest(siteId="x", step="search", message="a" * 50_001)

    def test_with_context_and_history(self) -> None:
        req = AiAssistRequest(
            siteId="x",
            step="controls",
            message="help",
            context={"organism": "Pf"},
            history=[{"role": "user", "content": "hi"}],
            model="gpt-4",
        )
        assert req.context == {"organism": "Pf"}
        assert len(req.history) == 1
        assert req.model == "gpt-4"


# ── Gene set schemas ─────────────────────────────────────────────────────────


class TestCreateGeneSetRequest:
    def test_valid(self) -> None:
        req = CreateGeneSetRequest(
            name="My Genes", siteId="plasmodb", geneIds=["G1", "G2"]
        )
        assert req.name == "My Genes"
        assert req.site_id == "plasmodb"
        assert req.gene_ids == ["G1", "G2"]
        assert req.source == "paste"  # default
        assert req.wdk_strategy_id is None
        assert req.wdk_step_id is None
        assert req.search_name is None
        assert req.record_type is None
        assert req.parameters is None

    def test_name_max_length(self) -> None:
        req = CreateGeneSetRequest(name="a" * 200, siteId="x", geneIds=["G1"])
        assert len(req.name) == 200
        with pytest.raises(ValidationError):
            CreateGeneSetRequest(name="a" * 201, siteId="x", geneIds=["G1"])

    def test_source_values(self) -> None:
        for src in ("strategy", "paste", "upload", "derived", "saved"):
            req = CreateGeneSetRequest(name="X", siteId="x", geneIds=["G1"], source=src)
            assert req.source == src

    def test_invalid_source(self) -> None:
        with pytest.raises(ValidationError):
            CreateGeneSetRequest(
                name="X",
                siteId="x",
                geneIds=["G1"],
                source="invalid",  # type: ignore[arg-type]
            )

    def test_with_wdk_fields(self) -> None:
        req = CreateGeneSetRequest(
            name="WDK Set",
            siteId="plasmodb",
            geneIds=["G1"],
            source="strategy",
            wdkStrategyId=42,
            wdkStepId=99,
            searchName="GenesByOrganism",
            recordType="gene",
            parameters={"org": "Pf"},
        )
        assert req.wdk_strategy_id == 42
        assert req.wdk_step_id == 99
        assert req.search_name == "GenesByOrganism"

    def test_serialization_by_alias(self) -> None:
        req = CreateGeneSetRequest(name="X", siteId="x", geneIds=["G1"])
        data = req.model_dump(by_alias=True)
        assert "siteId" in data
        assert "geneIds" in data
        assert "wdkStrategyId" in data
        assert "wdkStepId" in data
        assert "searchName" in data
        assert "recordType" in data


class TestGeneSetResponse:
    def test_construction(self) -> None:
        resp = GeneSetResponse(
            id="gs1",
            name="Test Set",
            siteId="plasmodb",
            geneIds=["G1", "G2", "G3"],
            source="paste",
            geneCount=3,
            createdAt="2026-03-06T00:00:00Z",
        )
        assert resp.id == "gs1"
        assert resp.gene_count == 3
        assert resp.parent_set_ids == []
        assert resp.operation is None
        assert resp.step_count == 1  # default

    def test_derived_set(self) -> None:
        resp = GeneSetResponse(
            id="gs2",
            name="Derived",
            siteId="x",
            geneIds=["G1"],
            source="derived",
            geneCount=1,
            parentSetIds=["gs1", "gs0"],
            operation="intersect",
            createdAt="2026-03-06T00:00:00Z",
        )
        assert resp.source == "derived"
        assert resp.parent_set_ids == ["gs1", "gs0"]
        assert resp.operation == "intersect"

    def test_serialization_by_alias(self) -> None:
        resp = GeneSetResponse(
            id="gs1",
            name="X",
            siteId="x",
            geneIds=["G1"],
            source="paste",
            geneCount=1,
            createdAt="2026-01-01",
        )
        data = resp.model_dump(by_alias=True)
        assert "siteId" in data
        assert "geneIds" in data
        assert "geneCount" in data
        assert "wdkStrategyId" in data
        assert "wdkStepId" in data
        assert "searchName" in data
        assert "recordType" in data
        assert "parentSetIds" in data
        assert "createdAt" in data
        assert "stepCount" in data


class TestSetOperationRequest:
    def test_valid(self) -> None:
        req = SetOperationRequest(
            setAId="gs1", setBId="gs2", operation="intersect", name="Intersection"
        )
        assert req.set_a_id == "gs1"
        assert req.set_b_id == "gs2"
        assert req.operation == "intersect"
        assert req.name == "Intersection"

    def test_name_max_length(self) -> None:
        req = SetOperationRequest(
            setAId="a", setBId="b", operation="union", name="x" * 200
        )
        assert len(req.name) == 200
        with pytest.raises(ValidationError):
            SetOperationRequest(
                setAId="a", setBId="b", operation="union", name="x" * 201
            )

    def test_serialization_by_alias(self) -> None:
        req = SetOperationRequest(setAId="a", setBId="b", operation="minus", name="X")
        data = req.model_dump(by_alias=True)
        assert "setAId" in data
        assert "setBId" in data


class TestGeneSetEnrichRequest:
    def test_valid(self) -> None:
        req = GeneSetEnrichRequest(enrichmentTypes=["go_function", "pathway"])
        assert req.enrichment_types == ["go_function", "pathway"]

    def test_missing_required(self) -> None:
        with pytest.raises(ValidationError):
            GeneSetEnrichRequest()  # type: ignore[call-arg]


class TestRunGeneSetAnalysisRequest:
    def test_valid(self) -> None:
        req = RunGeneSetAnalysisRequest(analysisName="go_enrichment")
        assert req.analysis_name == "go_enrichment"
        assert req.parameters == {}

    def test_with_params(self) -> None:
        req = RunGeneSetAnalysisRequest(
            analysisName="pathway", parameters={"threshold": "0.05"}
        )
        assert req.parameters == {"threshold": "0.05"}


# ── SSE helpers ──────────────────────────────────────────────────────────────


class TestSSEHeaders:
    def test_required_headers(self) -> None:
        assert SSE_HEADERS["Cache-Control"] == "no-cache"
        assert SSE_HEADERS["Connection"] == "keep-alive"
        assert SSE_HEADERS["X-Accel-Buffering"] == "no"


class TestSSEStream:
    async def test_basic_stream(self) -> None:
        """Producer sends a progress then a done event."""

        async def producer(send):
            await send({"type": "progress", "data": {"percent": 50}})
            await send({"type": "done", "data": {"result": "ok"}})

        frames: list[str] = []
        async for frame in sse_stream(producer, {"done"}):
            frames.append(frame)

        assert len(frames) == 2
        assert frames[0] == f"event: progress\ndata: {json.dumps({'percent': 50})}\n\n"
        assert frames[1] == f"event: done\ndata: {json.dumps({'result': 'ok'})}\n\n"

    async def test_terminates_on_end_event(self) -> None:
        """Stream should stop after seeing an end event, even if producer would send more."""

        async def producer(send):
            await send({"type": "progress", "data": {}})
            await send({"type": "error", "data": {"msg": "fail"}})
            # This should never be yielded:
            await send({"type": "progress", "data": {"extra": True}})

        frames: list[str] = []
        async for frame in sse_stream(producer, {"done", "error"}):
            frames.append(frame)

        assert len(frames) == 2
        assert "error" in frames[1]

    async def test_default_event_type(self) -> None:
        """Events without 'type' default to 'experiment_progress'."""

        async def producer(send):
            await send({"data": {"x": 1}})
            await send({"type": "done", "data": {}})

        frames: list[str] = []
        async for frame in sse_stream(producer, {"done"}):
            frames.append(frame)

        assert len(frames) == 2
        assert frames[0].startswith("event: experiment_progress")

    async def test_default_data(self) -> None:
        """Events without 'data' default to empty dict."""

        async def producer(send):
            await send({"type": "done"})

        frames: list[str] = []
        async for frame in sse_stream(producer, {"done"}):
            frames.append(frame)

        assert len(frames) == 1
        assert "data: {}" in frames[0]

    async def test_multiple_end_event_types(self) -> None:
        """Any event type in the end set terminates the stream."""

        async def producer(send):
            await send({"type": "completed", "data": {}})

        frames: list[str] = []
        async for frame in sse_stream(producer, {"completed", "error", "cancelled"}):
            frames.append(frame)

        assert len(frames) == 1
        assert "completed" in frames[0]


# ── Cross-schema integration: model_validate from JSON dicts ─────────────────


class TestModelValidateFromJSON:
    """Test model_validate with raw dict input, simulating JSON deserialization."""

    def test_chat_request_from_json(self) -> None:
        raw = {
            "siteId": "plasmodb",
            "message": "Find genes",
            "strategyId": str(uuid4()),
            "provider": "anthropic",
            "model": "claude-3",
            "reasoningEffort": "high",
            "mentions": [{"type": "strategy", "id": "s1", "displayName": "My Strat"}],
        }
        req = ChatRequest.model_validate(raw)
        assert req.site_id == "plasmodb"
        assert req.provider == "anthropic"
        assert req.model_id == "claude-3"
        assert len(req.mentions) == 1

    def test_experiment_request_from_json(self) -> None:
        raw = {
            "siteId": "plasmodb",
            "recordType": "gene",
            "mode": "multi-step",
            "searchName": "GenesByOrganism",
            "parameters": {"organism": "Pf"},
            "positiveControls": ["G1", "G2"],
            "negativeControls": ["G3"],
            "controlsSearchName": "GenesByLocusTag",
            "controlsParamName": "ds_gene_ids",
            "enableCrossValidation": True,
            "kFolds": 7,
            "enrichmentTypes": ["go_function", "pathway"],
            "name": "Test Experiment",
            "description": "A test",
            "optimizationBudget": 50,
            "sortDirection": "DESC",
        }
        req = CreateExperimentRequest.model_validate(raw)
        assert req.mode == "multi-step"
        assert req.k_folds == 7
        assert req.enrichment_types == ["go_function", "pathway"]
        assert req.sort_direction == "DESC"
        assert req.optimization_budget == 50

    def test_strategy_response_roundtrip(self) -> None:
        """Build a StrategyResponse, serialize by alias, validate it back."""
        now = datetime.now(UTC)
        sid = uuid4()
        original = StrategyResponse(
            id=sid,
            name="Roundtrip",
            siteId="toxodb",
            recordType="gene",
            createdAt=now,
            updatedAt=now,
            stepCount=2,
            resultCount=100,
            isSaved=True,
        )
        data = original.model_dump(by_alias=True, mode="json")
        restored = StrategyResponse.model_validate(data)
        assert restored.id == sid
        assert restored.name == "Roundtrip"
        assert restored.site_id == "toxodb"
        assert restored.step_count == 2
        assert restored.result_count == 100
        assert restored.is_saved is True

    def test_plan_node_roundtrip(self) -> None:
        """Build a nested PlanNode tree, serialize, validate back."""
        leaf1 = PlanNode(searchName="A", parameters={"k": "v"})
        leaf2 = PlanNode(searchName="B")
        combine = PlanNode(
            searchName="C",
            primaryInput=leaf1,
            secondaryInput=leaf2,
            operator="INTERSECT",
        )
        plan = StrategyPlan(recordType="gene", root=combine)
        data = plan.model_dump(mode="json")
        restored = StrategyPlan.model_validate(data)
        assert restored.root.operator == "INTERSECT"
        assert restored.root.primaryInput is not None
        assert restored.root.primaryInput.searchName == "A"
        assert restored.root.secondaryInput is not None

    def test_gene_set_response_roundtrip(self) -> None:
        original = GeneSetResponse(
            id="gs1",
            name="Test",
            siteId="plasmodb",
            geneIds=["G1", "G2"],
            source="paste",
            geneCount=2,
            createdAt="2026-03-06T00:00:00Z",
        )
        data = original.model_dump(by_alias=True, mode="json")
        restored = GeneSetResponse.model_validate(data)
        assert restored.id == "gs1"
        assert restored.gene_count == 2
        assert restored.gene_ids == ["G1", "G2"]
