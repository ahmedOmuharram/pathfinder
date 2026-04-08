"""Integration tests for the PathFinder v2 agent pipeline.

Mocks ONLY the LLM (via FunctionModel / TestModel). Everything else is real:
real domain objects, real services, real StrategySession, real AgentToolState,
real plan models. HTTP calls to plasmodb.org are intercepted with respx
at the httpx transport level — service code runs unmodified.
"""

import asyncio
from typing import Any

import pytest
import respx
from pydantic_ai import RunContext, capture_run_messages
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage, UsageLimits

from pathfinder.ai.agents.discovery import discovery_agent
from pathfinder.ai.agents.state import AgentToolState, SearchOverview
from pathfinder.ai.orchestration.classifier import Intent, classify_request
from pathfinder.ai.orchestration.deps import AgentDeps
from pathfinder.ai.orchestration.pipeline import create_pipeline
from pathfinder.ai.tools.standalone._plan_models import (
    PlanCreatedResponse,
    PlannedConnectionInput,
    PlannedStepInput,
)
from pathfinder.ai.tools.standalone.plan import create_plan, submit_plan
from pathfinder.domain.strategy.ast import PlanStepNode
from pathfinder.domain.strategy.plan import PlanStatus, StepType, StrategyPlan
from pathfinder.domain.strategy.session import StrategySession
from pathfinder.platform.tool_errors import ToolErrorPayload

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_deps(site_id: str = "plasmodb") -> AgentDeps:
    """Build real AgentDeps with real StrategySession and AgentToolState."""
    session = StrategySession(site_id=site_id)
    return AgentDeps(
        site_id=site_id,
        strategy_session=session,
        agent_state=AgentToolState(),
        event_queue=asyncio.Queue(),
    )


def _make_run_context(deps: AgentDeps) -> RunContext[AgentDeps]:
    """Build a real RunContext for standalone tool calls.

    The standalone tool functions (create_plan, submit_plan) accept
    ``RunContext[AgentDeps]``.  We construct a real ``RunContext`` with
    a ``TestModel`` placeholder — only ``ctx.deps`` is read by these tools.
    """
    return RunContext[AgentDeps](
        deps=deps,
        model=TestModel(),
        usage=RunUsage(),
    )


# ---------------------------------------------------------------------------
# WDK response fixtures (based on real plasmodb.org API shape)
# ---------------------------------------------------------------------------

_WDK_RECORD_TYPES_RESPONSE: list[object] = [
    {
        "urlSegment": "transcript",
        "fullName": "TranscriptRecordClasses.TranscriptRecordClass",
        "displayName": "Gene",
        "displayNamePlural": "Genes",
        "shortDisplayName": "Gene",
        "description": "Gene/transcript records",
        "recordIdAttributeName": "source_id",
        "primaryKeyColumnRefs": ["source_id", "project_id"],
        "useBasket": True,
        "hasAllRecordsQuery": True,
    },
]

_WDK_SEARCHES_RESPONSE: list[object] = [
    {
        "urlSegment": "GenesByTaxon",
        "fullName": "GeneQuestions.GenesByTaxon",
        "displayName": "Taxon",
        "shortDisplayName": "Taxon",
        "description": "Find genes by taxon (organism).",
        "summary": "Find genes by taxon (organism).",
        "outputRecordClassName": "TranscriptRecordClasses.TranscriptRecordClass",
        "isAnalyzable": True,
        "isCacheable": True,
        "paramNames": ["organism"],
        "groups": [],
        "defaultAttributes": ["source_id"],
        "defaultSorting": [],
        "filters": [],
        "properties": {},
    },
    {
        "urlSegment": "GenesByText",
        "fullName": "GeneQuestions.GenesByText",
        "displayName": "Text",
        "shortDisplayName": "Text",
        "description": "Find genes matching a text term.",
        "summary": "Find genes matching a text term.",
        "outputRecordClassName": "TranscriptRecordClasses.TranscriptRecordClass",
        "isAnalyzable": True,
        "isCacheable": True,
        "paramNames": ["text_expression"],
        "groups": [],
        "defaultAttributes": ["source_id"],
        "defaultSorting": [],
        "filters": [],
        "properties": {},
    },
]

_WDK_SEARCH_DETAIL_RESPONSE: object = {
    "searchData": {
        "urlSegment": "GenesByTaxon",
        "fullName": "GeneQuestions.GenesByTaxon",
        "displayName": "Taxon",
        "shortDisplayName": "Taxon",
        "description": "Find genes by taxon (organism).",
        "summary": "Find genes by taxon (organism).",
        "outputRecordClassName": "TranscriptRecordClasses.TranscriptRecordClass",
        "isAnalyzable": True,
        "isCacheable": True,
        "paramNames": ["organism"],
        "groups": [
            {
                "name": "default",
                "displayName": "Default",
                "description": "",
                "isVisible": True,
                "displayType": "",
                "parameters": ["organism"],
            }
        ],
        "parameters": [
            {
                "name": "organism",
                "displayName": "Organism",
                "help": "Select one or more organisms.",
                "type": "multi-pick-vocabulary",
                "isVisible": True,
                "group": "default",
                "isReadOnly": False,
                "allowEmptyValue": False,
                "visibleHelp": None,
                "visibleHelpPosition": None,
                "dependentParams": [],
                "initialDisplayValue": None,
                "properties": {},
                "vocabulary": [
                    ["Plasmodium falciparum 3D7", "P. falciparum 3D7", None],
                    ["Plasmodium vivax Sal-1", "P. vivax Sal-1", None],
                ],
                "countOnlyLeaves": False,
                "displayType": "treeBox",
                "minSelectedCount": 1,
                "maxSelectedCount": None,
            }
        ],
        "defaultAttributes": ["source_id"],
        "defaultSorting": [],
        "filters": [],
        "properties": {},
    },
    "validation": {
        "level": "NONE",
        "isValid": True,
        "errors": {"general": [], "byKey": {}},
    },
}


# ---------------------------------------------------------------------------
# Test 1: Classifier with real deps
# ---------------------------------------------------------------------------


class TestClassifierWithRealDeps:
    """Test the rule-based classifier with real StrategySession and StrategyGraph."""

    def test_new_strategy_no_graph(self) -> None:
        """Creation keywords without a graph produce NEW_STRATEGY."""
        deps = _make_deps()
        result = classify_request(
            "Find malaria genes in P. falciparum",
            graph=deps.strategy_session.graph,
        )
        assert result is not None
        assert result.intent == Intent.NEW_STRATEGY
        assert result.confidence == 0.85

    def test_extend_strategy_with_real_graph(self) -> None:
        """Extension keywords with a real populated graph produce EXTEND_STRATEGY."""
        deps = _make_deps()
        graph = deps.strategy_session.create_graph("Test Strategy")
        step = PlanStepNode(search_name="GenesByTaxon", display_name="Taxon")
        graph.add_step(step)

        result = classify_request(
            "Also filter by expression data",
            graph=graph,
        )
        assert result is not None
        assert result.intent == Intent.EXTEND_STRATEGY
        assert result.confidence == 0.80

    def test_edit_strategy_with_real_graph(self) -> None:
        """Edit keywords with a real graph produce EDIT_STRATEGY."""
        deps = _make_deps()
        graph = deps.strategy_session.create_graph("Test Strategy")
        step = PlanStepNode(search_name="GenesByTaxon", display_name="Taxon")
        graph.add_step(step)

        result = classify_request(
            "Change the organism to P. vivax",
            graph=graph,
        )
        assert result is not None
        assert result.intent == Intent.EDIT_STRATEGY
        assert result.confidence == 0.75

    def test_question_intent(self) -> None:
        """Interrogative pattern produces QUESTION."""
        result = classify_request("What does PF3D7_1133400 do?")
        assert result is not None
        assert result.intent == Intent.QUESTION
        assert result.confidence == 0.85

    def test_plan_approval_with_pending_plan(self) -> None:
        """Approval pattern with pending plan produces EDIT_STRATEGY."""
        deps = _make_deps()
        result = classify_request(
            "looks good",
            graph=deps.strategy_session.graph,
            has_pending_plan=True,
        )
        assert result is not None
        assert result.intent == Intent.EDIT_STRATEGY
        assert result.confidence == 0.95

    def test_ambiguous_returns_none_for_llm_tier(self) -> None:
        """Ambiguous creation keywords with existing graph fall through to LLM."""
        deps = _make_deps()
        graph = deps.strategy_session.create_graph("Test Strategy")
        step = PlanStepNode(search_name="GenesByTaxon", display_name="Taxon")
        graph.add_step(step)

        result = classify_request(
            "Find genes expressed in the liver",
            graph=graph,
        )
        assert result is None


# ---------------------------------------------------------------------------
# Test 2: Pipeline state machine — full traversal with real objects
# ---------------------------------------------------------------------------


class TestPipelineStateMachineFullTraversal:
    """Drive the state machine through all phases and verify transitions."""

    def test_full_discovery_to_completed(self) -> None:
        """Full traversal: discovery -> planning -> execution -> verification -> completed."""
        pipeline = create_pipeline()

        assert pipeline.current_phase == "discovery"
        assert pipeline.is_done is False

        # Discovery phase
        pipeline.send("analyze")
        state_ids = {s.id for s in pipeline.configuration}
        assert "analyzing" in state_ids

        pipeline.send("finish_discovery")
        assert pipeline.current_phase == "planning"

        # Planning phase
        pipeline.send("submit_draft")
        state_ids = {s.id for s in pipeline.configuration}
        assert "awaiting_approval" in state_ids

        pipeline.send("approve")
        assert pipeline.current_phase == "execution"

        # Execution phase
        pipeline.send("finish_execution")
        assert pipeline.current_phase == "verification"

        # Verification phase
        pipeline.send("present")
        state_ids = {s.id for s in pipeline.configuration}
        assert "presenting" in state_ids

        pipeline.send("finish_verification")
        assert pipeline.current_phase == "completed"
        assert pipeline.is_done is True

        # Verify retry counts
        assert pipeline.retry_counts["discovery"] == 1
        assert pipeline.retry_counts["planning"] == 1
        assert pipeline.retry_counts["execution"] == 1

    def test_replan_cycle_within_budget(self) -> None:
        """Execution replan returns to planning, then re-executes."""
        pipeline = create_pipeline()

        # Advance to execution
        pipeline.send("finish_discovery")
        pipeline.send("submit_draft")
        pipeline.send("approve")
        assert pipeline.current_phase == "execution"

        # Replan (within budget)
        pipeline.send("replan")
        assert pipeline.current_phase == "planning"
        assert pipeline.retry_counts["planning"] == 2

        # Plan revision cycle
        pipeline.send("submit_draft")
        pipeline.send("request_revision")
        state_ids = {s.id for s in pipeline.configuration}
        assert "revising" in state_ids

        pipeline.send("resubmit")
        pipeline.send("approve")
        assert pipeline.current_phase == "execution"

        # Now complete
        pipeline.send("finish_execution")
        pipeline.send("finish_verification")
        assert pipeline.current_phase == "completed"
        assert pipeline.is_done is True
        # 7 = discovery + planning*2 + execution*2 + verification + completed
        assert pipeline._transition_count == 7

    def test_abort_from_any_phase(self) -> None:
        """Abort transitions from each phase produce 'failed' state."""
        # Abort from discovery
        pipeline = create_pipeline()
        pipeline.send("abort_discovery")
        assert pipeline.current_phase == "failed"
        assert pipeline.is_done is True

        # Abort from execution
        pipeline = create_pipeline()
        pipeline.send("finish_discovery")
        pipeline.send("submit_draft")
        pipeline.send("approve")
        pipeline.send("abort_execution")
        assert pipeline.current_phase == "failed"

    def test_retry_budget_exhausted_blocks_replan(self) -> None:
        """After exhausting retry budget, replan is blocked."""
        pipeline = create_pipeline()
        pipeline.send("finish_discovery")
        pipeline.send("submit_draft")
        pipeline.send("approve")

        # Exhaust 3 retries
        for _ in range(3):
            pipeline.send("replan")
            pipeline.send("submit_draft")
            pipeline.send("approve")

        # 4th replan: guard fails, stays in execution.
        # Execution count stays at 3 because the guard-blocked transition
        # never enters execution (so the tracker doesn't increment).
        pipeline.send("replan")
        assert pipeline.current_phase == "execution"
        assert pipeline.retry_counts["execution"] == 3


# ---------------------------------------------------------------------------
# Test 3: Discovery agent with FunctionModel + respx HTTP mocking
# ---------------------------------------------------------------------------


class TestDiscoveryAgentWithFunctionModel:
    """Run the discovery agent with a FunctionModel that calls real tools.

    HTTP calls to plasmodb.org are intercepted by respx at the httpx transport
    level, so the full service stack (tool -> service -> integration -> httpx)
    runs unmodified.
    """

    @pytest.mark.asyncio
    async def test_discovery_agent_calls_get_search_overview(self) -> None:
        """FunctionModel drives the agent to call get_search_overview.

        Verifies:
        - The tool call populates discovered_searches in agent state
        - The agent produces a string result
        - Tool calls were actually made (via capture_run_messages)
        """
        deps = _make_deps()
        call_count = 0

        def discovery_model(
            messages: list[object], info: AgentInfo
        ) -> ModelResponse:
            nonlocal call_count
            call_count += 1

            # First call: invoke get_search_overview
            if call_count == 1:
                return ModelResponse(
                    parts=[
                        ToolCallPart(
                            tool_name="get_search_overview",
                            args={
                                "search_name": "GenesByTaxon",
                                "record_type": "transcript",
                            },
                            tool_call_id="call_1",
                        )
                    ]
                )

            # Second call: return final text
            return ModelResponse(
                parts=[TextPart(content="Found GenesByTaxon search for organism filtering.")]
            )

        # Mock the WDK HTTP calls at the httpx level.
        # The VEuPathDBClient uses httpx.AsyncClient with base_url.
        # respx intercepts based on full URL pattern.
        with respx.mock(assert_all_called=False) as router:
            # Mock the catalog load (record types)
            router.get(url__regex=r".*/record-types$").respond(
                json=_WDK_RECORD_TYPES_RESPONSE,
            )
            # Mock the searches list (used by catalog load)
            router.get(url__regex=r".*/record-types/transcript/searches$").respond(
                json=_WDK_SEARCHES_RESPONSE,
            )
            # Mock the search detail endpoint (used by get_search_overview)
            router.get(
                url__regex=r".*/record-types/transcript/searches/GenesByTaxon",
            ).respond(
                json=_WDK_SEARCH_DETAIL_RESPONSE,
            )
            # Mock the dataset report (used by catalog load for dataset summaries)
            router.post(url__regex=r".*/record-types/dataset/searches/.*/reports/.*").respond(
                json={"records": []},
            )
            # Mock the ontology endpoint
            router.get(url__regex=r".*/ontologies/.*").respond(
                json={"treeNodes": []},
            )
            # Mock any other GET to record-types to avoid failures
            router.get(url__regex=r".*/record-types/.*").respond(json=[])
            # Catch-all for site-search
            router.post(url__regex=r".*/site-search").respond(
                json={"searchResults": [], "totalCount": 0},
            )

            with capture_run_messages() as messages:
                result = await discovery_agent.run(
                    "Find genes by organism in Plasmodium",
                    deps=deps,
                    model=FunctionModel(discovery_model),
                    usage_limits=UsageLimits(request_limit=5),
                )

        # Verify agent produced a string result
        assert isinstance(result.output, str)
        assert "GenesByTaxon" in result.output

        # Verify the discovery gate was populated
        assert deps.agent_state.is_search_discovered("GenesByTaxon")
        overview = deps.agent_state.get_overview("GenesByTaxon")
        assert overview is not None
        assert overview.search_name == "GenesByTaxon"
        assert overview.display_name == "Taxon"
        assert overview.record_type == "transcript"
        assert "organism" in overview.parameter_names

        # Verify tool calls were made (capture_run_messages)
        all_messages = messages[:]
        tool_call_found = False
        for msg in all_messages:
            if hasattr(msg, "parts"):
                for part in msg.parts:
                    if hasattr(part, "tool_name") and part.tool_name == "get_search_overview":
                        tool_call_found = True
        assert tool_call_found, "Expected get_search_overview tool call in messages"


# ---------------------------------------------------------------------------
# Test 4: Plan tools with real agent state (no network, no testcontainers)
# ---------------------------------------------------------------------------


class TestPlanToolsWithRealAgentState:
    """Test create_plan and submit_plan as standalone functions.

    These tools are pure service-level calls that operate on AgentToolState.
    No network or testcontainers needed.
    """

    @pytest.mark.asyncio
    async def test_create_plan_populates_agent_state(self) -> None:
        """create_plan stores a StrategyPlan in agent_state.active_plan."""
        deps = _make_deps()
        # Pre-register search in discovery gate (required for submit_plan validation)
        deps.agent_state.register_search(
            "GenesByTaxon",
            SearchOverview(
                search_name="GenesByTaxon",
                display_name="Taxon",
                record_type="transcript",
                description="Find genes by taxon.",
                parameter_names=["organism"],
                required_params=["organism"],
            ),
        )

        ctx = _make_run_context(deps)
        result = await create_plan(
            ctx,
            title="Malaria Gene Strategy",
            description="Find P. falciparum genes by organism",
            rationale="GenesByTaxon is the most direct search for organism filtering",
            steps=[
                PlannedStepInput(
                    id="step_1",
                    search_name="GenesByTaxon",
                    display_name="Genes by Taxon",
                    record_type="transcript",
                    step_type=StepType.LEAF,
                    parameters={"organism": '["Plasmodium falciparum 3D7"]'},
                ),
            ],
            connections=[],
        )

        # Verify response
        assert isinstance(result, PlanCreatedResponse), f"Expected PlanCreatedResponse, got: {result}"
        assert result.title == "Malaria Gene Strategy"
        assert result.step_count == 1

        # Verify plan in agent state
        plan = deps.agent_state.active_plan
        assert plan is not None
        assert plan.title == "Malaria Gene Strategy"
        assert plan.status == PlanStatus.DRAFT
        assert len(plan.steps) == 1
        assert plan.steps[0].search_name == "GenesByTaxon"
        assert plan.steps[0].display_name == "Genes by Taxon"
        assert plan.steps[0].step_type == StepType.LEAF
        assert "organism" in plan.steps[0].parameters
        assert plan.steps[0].parameters["organism"].value == '["Plasmodium falciparum 3D7"]'

    @pytest.mark.asyncio
    async def test_submit_plan_changes_status_to_presented(self) -> None:
        """submit_plan validates and sets status to PRESENTED, emitting events."""
        deps = _make_deps()
        deps.agent_state.register_search(
            "GenesByTaxon",
            SearchOverview(
                search_name="GenesByTaxon",
                display_name="Taxon",
                record_type="transcript",
                description="Find genes by taxon.",
                parameter_names=["organism"],
                required_params=["organism"],
            ),
        )

        ctx = _make_run_context(deps)

        # Create the plan first
        await create_plan(
            ctx,
            title="Submit Test Plan",
            description="Test plan submission",
            rationale="Testing submit_plan",
            steps=[
                PlannedStepInput(
                    id="step_a",
                    search_name="GenesByTaxon",
                    display_name="Genes by Taxon",
                    record_type="transcript",
                    step_type=StepType.LEAF,
                    parameters={"organism": '["Plasmodium falciparum 3D7"]'},
                ),
            ],
            connections=[],
        )

        # Submit the plan
        result = await submit_plan(ctx)

        # Verify it returned the plan (not an error)
        assert isinstance(result, StrategyPlan), f"Expected StrategyPlan, got: {result}"
        assert result.status == PlanStatus.PRESENTED
        assert result.title == "Submit Test Plan"

        # Verify events were emitted
        assert deps.event_queue is not None
        events: list[Any] = []
        while not deps.event_queue.empty():
            events.append(deps.event_queue.get_nowait())

        event_types = [e["type"] for e in events]
        assert "plan_presented" in event_types
        assert "graph_plan" in event_types

    @pytest.mark.asyncio
    async def test_create_multi_step_plan_with_connections(self) -> None:
        """Multi-step plan with connections validates topology."""
        deps = _make_deps()
        deps.agent_state.register_search(
            "GenesByTaxon",
            SearchOverview(
                search_name="GenesByTaxon",
                display_name="Taxon",
                record_type="transcript",
                description="Find genes by taxon.",
                parameter_names=["organism"],
                required_params=["organism"],
            ),
        )
        deps.agent_state.register_search(
            "GenesByText",
            SearchOverview(
                search_name="GenesByText",
                display_name="Text",
                record_type="transcript",
                description="Find genes by text.",
                parameter_names=["text_expression"],
                required_params=["text_expression"],
            ),
        )

        ctx = _make_run_context(deps)
        result = await create_plan(
            ctx,
            title="Intersect Taxon and Text",
            description="Find Plasmodium genes matching a keyword",
            rationale="Intersect organism filter with text search",
            steps=[
                PlannedStepInput(
                    id="leaf_1",
                    search_name="GenesByTaxon",
                    display_name="Genes by Taxon",
                    record_type="transcript",
                    step_type=StepType.LEAF,
                    parameters={"organism": '["Plasmodium falciparum 3D7"]'},
                ),
                PlannedStepInput(
                    id="leaf_2",
                    search_name="GenesByText",
                    display_name="Genes by Text",
                    record_type="transcript",
                    step_type=StepType.LEAF,
                    parameters={"text_expression": "kinase"},
                ),
                PlannedStepInput(
                    id="combine_1",
                    search_name="boolean_question",
                    display_name="Intersect",
                    record_type="transcript",
                    step_type=StepType.COMBINE,
                    operator="INTERSECT",
                ),
            ],
            connections=[
                PlannedConnectionInput(from_step="leaf_1", to_step="combine_1", input_type="primary"),
                PlannedConnectionInput(from_step="leaf_2", to_step="combine_1", input_type="secondary"),
            ],
        )

        assert isinstance(result, PlanCreatedResponse), f"Expected PlanCreatedResponse, got: {result}"
        assert result.step_count == 3

        plan = deps.agent_state.active_plan
        assert plan is not None
        assert len(plan.steps) == 3
        assert len(plan.connections) == 2

        # Verify topological ordering
        ordered = plan.steps_in_dependency_order()
        step_ids = [s.id for s in ordered]
        # Leaves must come before combine
        assert step_ids.index("leaf_1") < step_ids.index("combine_1")
        assert step_ids.index("leaf_2") < step_ids.index("combine_1")

    @pytest.mark.asyncio
    async def test_create_plan_rejects_invalid_topology(self) -> None:
        """create_plan returns a ToolErrorPayload for broken connections."""
        deps = _make_deps()
        ctx = _make_run_context(deps)

        result = await create_plan(
            ctx,
            title="Bad Topology",
            description="References non-existent step",
            rationale="Testing error handling",
            steps=[
                PlannedStepInput(
                    id="step_x",
                    search_name="GenesByTaxon",
                    display_name="Genes by Taxon",
                    step_type=StepType.LEAF,
                ),
            ],
            connections=[
                PlannedConnectionInput(
                    from_step="step_x",
                    to_step="nonexistent_step",
                ),
            ],
        )

        # Should be a ToolErrorPayload, not a PlanCreatedResponse
        assert isinstance(result, ToolErrorPayload), f"Expected ToolErrorPayload, got: {result}"
        assert result.code == "TOPOLOGY_ERROR"
        assert result.ok is False

    @pytest.mark.asyncio
    async def test_plan_history_tracks_previous_plans(self) -> None:
        """Creating a second plan archives the first in plan_history."""
        deps = _make_deps()
        ctx = _make_run_context(deps)

        # First plan
        await create_plan(
            ctx,
            title="Plan A",
            description="First plan",
            rationale="Testing history",
            steps=[
                PlannedStepInput(
                    id="step_a1",
                    search_name="GenesByTaxon",
                    display_name="Genes by Taxon",
                    step_type=StepType.LEAF,
                ),
            ],
            connections=[],
        )

        first_plan = deps.agent_state.active_plan
        assert first_plan is not None
        assert first_plan.title == "Plan A"
        assert len(deps.agent_state.plan_history) == 0

        # Second plan — archives the first
        await create_plan(
            ctx,
            title="Plan B",
            description="Second plan",
            rationale="Revised approach",
            steps=[
                PlannedStepInput(
                    id="step_b1",
                    search_name="GenesByText",
                    display_name="Genes by Text",
                    step_type=StepType.LEAF,
                ),
            ],
            connections=[],
        )

        assert deps.agent_state.active_plan is not None
        assert deps.agent_state.active_plan.title == "Plan B"
        assert len(deps.agent_state.plan_history) == 1
        assert deps.agent_state.plan_history[0].title == "Plan A"
