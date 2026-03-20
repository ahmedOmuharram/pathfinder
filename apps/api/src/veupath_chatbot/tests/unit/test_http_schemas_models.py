from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from veupath_chatbot.transport.http import schemas
from veupath_chatbot.transport.http.schemas.chat import ChatMention
from veupath_chatbot.transport.http.schemas.experiments import (
    CreateExperimentRequest,
    CustomEnrichRequest,
    OverlapRequest,
    ThresholdSweepRequest,
)
from veupath_chatbot.transport.http.schemas.plan import PlanNode


def test_http_schemas_import_and_basic_model_parsing() -> None:
    now = datetime.now(UTC)

    health = schemas.HealthResponse(status="healthy", version="1", timestamp=now)
    assert health.status == "healthy"

    site = schemas.SiteResponse(
        id="plasmodb",
        name="PlasmoDB",
        displayName="PlasmoDB",
        baseUrl="https://plasmodb.org",
        projectId="PlasmoDB",
        isPortal=False,
    )
    assert site.display_name == "PlasmoDB"
    assert site.base_url.startswith("https://")

    chat = schemas.ChatRequest(siteId="plasmodb", message="hello", strategyId=None)
    assert chat.site_id == "plasmodb"

    msg = schemas.MessageResponse(
        role="assistant",
        content="hi",
        timestamp=now,
        toolCalls=[schemas.ToolCallResponse(id="t1", name="tool", arguments={"a": 1})],
    )
    assert msg.tool_calls
    assert msg.tool_calls[0].name == "tool"

    step = schemas.StepResponse(
        id="s1",
        kind="search",
        displayName="Step",
        recordType="gene",
        resultCount=5,
    )
    assert step.display_name == "Step"
    assert step.result_count == 5

    _ = schemas.OpenStrategyRequest(siteId="plasmodb", strategyId=uuid4())


# ── ChatRequest validation ──


def test_chat_request_valid() -> None:
    req = schemas.ChatRequest(siteId="plasmodb", message="hello")
    assert req.strategy_id is None


def test_chat_request_rejects_empty_message() -> None:
    with pytest.raises(ValidationError) as exc_info:
        schemas.ChatRequest(siteId="plasmodb", message="")
    errors = exc_info.value.errors()
    assert any("message" in str(e.get("loc", "")) for e in errors)


def test_chat_request_rejects_missing_site_id() -> None:
    with pytest.raises(ValidationError):
        schemas.ChatRequest.model_validate({"message": "hello"})


def test_chat_request_defaults() -> None:
    req = schemas.ChatRequest(siteId="plasmodb", message="hi")
    assert req.provider is None
    assert req.model_id is None
    assert req.reasoning_effort is None
    assert req.mentions == []


def test_chat_request_with_mentions() -> None:
    req = schemas.ChatRequest(
        siteId="plasmodb",
        message="check @strat",
        mentions=[ChatMention(type="strategy", id="s1", displayName="My Strategy")],
    )
    assert len(req.mentions) == 1
    assert req.mentions[0].display_name == "My Strategy"


# ── Strategy schemas ──


def test_strategy_response_summary_fields() -> None:
    now = datetime.now(UTC)
    resp = schemas.StrategyResponse(
        id=uuid4(),
        name="Strategy A",
        siteId="plasmodb",
        recordType="gene",
        stepCount=3,
        createdAt=now,
        updatedAt=now,
    )
    assert resp.step_count == 3
    assert resp.is_saved is False
    assert resp.steps == []  # default empty for list views


def test_open_strategy_request_requires_at_least_one_id() -> None:
    req = schemas.OpenStrategyRequest(siteId="plasmodb", strategyId=uuid4())
    assert req.strategy_id is not None


def test_create_strategy_request_validates_name_length() -> None:
    plan = schemas.StrategyPlan(
        recordType="gene",
        root=PlanNode(searchName="GenesByOrganism"),
    )
    req = schemas.CreateStrategyRequest(
        name="Valid Name",
        siteId="plasmodb",
        plan=plan,
    )
    assert req.name == "Valid Name"


def test_create_strategy_rejects_empty_name() -> None:
    plan = schemas.StrategyPlan(
        recordType="gene",
        root=PlanNode(searchName="GenesByOrganism"),
    )
    with pytest.raises(ValidationError) as exc_info:
        schemas.CreateStrategyRequest(name="", siteId="plasmodb", plan=plan)
    errors = exc_info.value.errors()
    assert any("name" in str(e.get("loc", "")) for e in errors)


# ── Experiment config schemas ──


def test_experiment_request_basic() -> None:
    req = CreateExperimentRequest(
        siteId="plasmodb",
        recordType="gene",
        positiveControls=["GENE1", "GENE2"],
        negativeControls=["GENE3"],
        controlsSearchName="GenesByLocusTag",
        controlsParamName="ds_gene_ids",
        searchName="GenesByOrganism",
        parameters={"organism": "Plasmodium falciparum"},
    )
    assert req.site_id == "plasmodb"
    assert req.mode == "single"
    assert req.enable_cross_validation is False
    assert req.k_folds == 5


def test_experiment_request_rejects_invalid_mode() -> None:
    with pytest.raises(ValidationError):
        CreateExperimentRequest(
            siteId="plasmodb",
            recordType="gene",
            positiveControls=["G1"],
            negativeControls=["G2"],
            controlsSearchName="GenesByLocusTag",
            controlsParamName="ds_gene_ids",
            mode="invalid_mode",
        )


def test_experiment_request_k_folds_bounds() -> None:
    base = {
        "siteId": "plasmodb",
        "recordType": "gene",
        "positiveControls": ["G1"],
        "negativeControls": ["G2"],
        "controlsSearchName": "GenesByLocusTag",
        "controlsParamName": "ds_gene_ids",
        "enableCrossValidation": True,
    }
    req = CreateExperimentRequest(**base, kFolds=3)
    assert req.k_folds == 3

    with pytest.raises(ValidationError):
        CreateExperimentRequest(**base, kFolds=1)

    with pytest.raises(ValidationError):
        CreateExperimentRequest(**base, kFolds=11)


def test_threshold_sweep_request_steps_bounds() -> None:
    base = {"parameterName": "score", "minValue": 0.0, "maxValue": 1.0}
    req = ThresholdSweepRequest(**base, steps=10)
    assert req.steps == 10

    with pytest.raises(ValidationError):
        ThresholdSweepRequest(**base, steps=2)

    with pytest.raises(ValidationError):
        ThresholdSweepRequest(**base, steps=51)


def test_overlap_request_requires_two_experiments() -> None:
    req = OverlapRequest(experimentIds=["exp-1", "exp-2"])
    assert len(req.experiment_ids) == 2

    with pytest.raises(ValidationError):
        OverlapRequest(experimentIds=["exp-1"])


def test_custom_enrich_request_validation() -> None:
    req = CustomEnrichRequest(geneSetName="Kinases", geneIds=["G1", "G2"])
    assert req.gene_set_name == "Kinases"

    with pytest.raises(ValidationError):
        CustomEnrichRequest(geneSetName="", geneIds=["G1"])

    with pytest.raises(ValidationError):
        CustomEnrichRequest(geneSetName="X", geneIds=[])


# ── Strategy plan / PlanNode schema ──


def test_strategy_plan_nested_structure() -> None:
    plan = schemas.StrategyPlan(
        recordType="gene",
        root=PlanNode(
            searchName="GenesByOrganism",
            parameters={"organism": "Plasmodium falciparum"},
        ),
    )
    assert plan.recordType == "gene"
    assert plan.root.searchName == "GenesByOrganism"


def test_plan_node_with_combine() -> None:
    leaf1 = PlanNode(searchName="GenesByOrganism")
    leaf2 = PlanNode(searchName="GenesByProduct")
    combined = PlanNode(
        searchName="GenesByOrganism",
        primaryInput=leaf1,
        secondaryInput=leaf2,
        operator="INTERSECT",
    )
    assert combined.operator == "INTERSECT"
    assert combined.secondaryInput is not None


# ── MessageResponse schema ──


def test_message_response_with_all_fields() -> None:
    now = datetime.now(UTC)
    msg = schemas.MessageResponse(
        role="assistant",
        content="Here's your analysis",
        timestamp=now,
        toolCalls=[
            schemas.ToolCallResponse(id="t1", name="search", arguments={"q": "abc"})
        ],
        citations=[{"id": "c1", "source": "pubmed", "title": "Citation"}],
        reasoning="Step-by-step analysis",
    )
    assert msg.role == "assistant"
    assert msg.tool_calls is not None
    assert len(msg.tool_calls) == 1
    assert msg.reasoning == "Step-by-step analysis"


def test_message_response_minimal() -> None:
    now = datetime.now(UTC)
    msg = schemas.MessageResponse(role="user", content="hello", timestamp=now)
    assert msg.citations is None
