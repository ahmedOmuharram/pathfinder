"""End-to-end streaming pipeline integration test.

Chains all 4 phases (discovery -> planning -> execution -> verification)
using FunctionModel (``model_id="mock/deterministic"``) and verifies SSE
event ordering, structured handoff flow, and graph state.

Only the LLM is mocked.  Domain models, services, and the full tool stack
run unmodified.  WDK HTTP calls are intercepted by ``respx`` at the httpx
transport level.  The ``DiscoveryService`` catalog is pre-populated so the
pipeline never loads the sentence-transformer embedding model.
"""

import asyncio

import pytest
import respx

from veupath_chatbot.ai.agents.state import AgentToolState
from veupath_chatbot.ai.orchestration.deps import AgentDeps
from veupath_chatbot.domain.strategy.plan import PlanStatus
from veupath_chatbot.domain.strategy.session import StrategySession
from veupath_chatbot.integrations.veupathdb.discovery import SearchCatalog
from veupath_chatbot.integrations.veupathdb.discovery_service import (
    get_discovery_service,
)
from veupath_chatbot.integrations.veupathdb.wdk_models import (
    WDKRecordType,
    WDKSearch,
)
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.chat.streaming import stream_pipeline

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_deps(site_id: str = "plasmodb") -> AgentDeps:
    """Build real AgentDeps with real StrategySession and AgentToolState."""
    session = StrategySession(site_id=site_id)
    # Create a graph so create_leaf_step has somewhere to add steps.
    session.create_graph("Test Strategy")
    return AgentDeps(
        site_id=site_id,
        strategy_session=session,
        agent_state=AgentToolState(),
        event_queue=asyncio.Queue(),
    )


def _prepopulate_catalog(site_id: str = "plasmodb") -> None:
    """Pre-populate the DiscoveryService catalog for a site.

    Bypasses catalog.load() entirely (which triggers sentence-transformer
    model download).  Sets ``_loaded = True`` so all downstream code that
    calls ``get_catalog()`` gets the pre-populated data immediately.
    """
    discovery = get_discovery_service()
    catalog = SearchCatalog(site_id)

    transcript_rt = WDKRecordType.model_validate({
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
    })

    taxon_search = WDKSearch.model_validate({
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
    })

    catalog._record_types = [transcript_rt]
    catalog._searches = {"transcript": [taxon_search]}
    catalog._loaded = True

    discovery._catalogs[site_id] = catalog


# ---------------------------------------------------------------------------
# WDK response fixtures (based on real plasmodb.org API shape)
# ---------------------------------------------------------------------------

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

_WDK_STEP_RESPONSE: object = {
    "id": 42,
    "displayName": "P. falciparum genes",
    "shortDisplayName": "P. falciparum genes",
    "customName": "P. falciparum genes",
    "baseCustomName": "P. falciparum genes",
    "isFiltered": False,
    "isStandard": True,
    "allowRevise": True,
    "recordClassName": "TranscriptRecordClasses.TranscriptRecordClass",
    "searchName": "GenesByTaxon",
    "searchConfig": {
        "parameters": {"organism": '["Plasmodium falciparum 3D7"]'},
        "wdkWeight": 10,
    },
    "displayPreferences": {
        "columnSelection": None,
        "sortColumns": [],
    },
    "estimatedSize": 5000,
    "hasCompleteAnalyses": False,
    "validation": {
        "level": "NONE",
        "isValid": True,
        "errors": {"general": [], "byKey": {}},
    },
}

def _setup_respx_router(router: respx.MockRouter) -> None:
    """Configure respx routes for the WDK endpoints hit during the pipeline.

    The catalog is pre-populated, so only search-detail, step CRUD, and
    strategy CRUD endpoints need mocking here.
    """
    # Search detail (used by get_search_overview)
    router.get(
        url__regex=r".*/record-types/transcript/searches/GenesByTaxon",
    ).respond(json=_WDK_SEARCH_DETAIL_RESPONSE)
    # User ID endpoint (used by StrategyAPI for step/strategy creation)
    router.get(url__regex=r".*/users/current$").respond(
        json={"id": 99999, "isGuest": True},
    )
    # Step creation (POST returns WDKIdentifier: {"id": <int>})
    router.post(url__regex=r".*/users/.*/steps$").respond(
        json={"id": 42},
    )
    # Step fetch (find_step after push: GET returns full WDKStep)
    router.get(url__regex=r".*/users/.*/steps/\d+$").respond(
        json=_WDK_STEP_RESPONSE,
    )
    # Strategy creation (POST returns WDKIdentifier: {"id": <int>})
    router.post(url__regex=r".*/users/.*/strategies$").respond(
        json={"id": 99},
    )
    # Step tree update
    router.put(url__regex=r".*/users/.*/strategies/\d+/step-tree$").respond(
        json={"stepId": 42},
    )
    # WDK session init (hits /app)
    router.get(url__regex=r".*/app.*").respond(200)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def _collect_events(
    deps: AgentDeps, message: str, model_id: str = "mock/deterministic"
) -> list[JSONObject]:
    """Run stream_pipeline and collect all emitted events."""
    return [event async for event in stream_pipeline(deps, message, model_id=model_id)]


class TestE2EPipelineEventOrdering:
    """Verify SSE event ordering and completeness across all 4 phases."""

    @pytest.mark.anyio
    async def test_message_end_is_last_event(self) -> None:
        """message_end MUST be the final event in the stream."""
        _prepopulate_catalog()
        deps = _make_deps()
        with respx.mock(assert_all_called=False, assert_all_mocked=False) as router:
            _setup_respx_router(router)
            events = await _collect_events(deps, "create step")

        assert len(events) > 0, "Pipeline emitted no events"
        assert events[-1].get("type") == "message_end"

    @pytest.mark.anyio
    async def test_assistant_message_exists(self) -> None:
        """At least one assistant_message event must exist."""
        _prepopulate_catalog()
        deps = _make_deps()
        with respx.mock(assert_all_called=False, assert_all_mocked=False) as router:
            _setup_respx_router(router)
            events = await _collect_events(deps, "create step")

        event_types = [e.get("type") for e in events]
        assert "assistant_message" in event_types

    @pytest.mark.anyio
    async def test_tool_call_start_end_pairing(self) -> None:
        """Every tool_call_start must have a matching tool_call_end."""
        _prepopulate_catalog()
        deps = _make_deps()
        with respx.mock(assert_all_called=False, assert_all_mocked=False) as router:
            _setup_respx_router(router)
            events = await _collect_events(deps, "create step")

        start_ids: list[str] = []
        end_ids: list[str] = []
        for event in events:
            if event.get("type") == "tool_call_start":
                data = event.get("data", {})
                if isinstance(data, dict):
                    start_ids.append(str(data.get("id", "")))
            elif event.get("type") == "tool_call_end":
                data = event.get("data", {})
                if isinstance(data, dict):
                    end_ids.append(str(data.get("id", "")))

        assert len(start_ids) > 0, "No tool_call_start events found"
        assert len(end_ids) > 0, "No tool_call_end events found"
        # Every start must have a matching end
        for start_id in start_ids:
            assert start_id in end_ids, (
                f"tool_call_start id={start_id} has no matching tool_call_end"
            )


class TestE2EPipelinePhaseExecution:
    """Verify that events from each phase appear in the stream."""

    @pytest.mark.anyio
    async def test_discovery_phase_tool_calls(self) -> None:
        """Discovery phase calls get_search_overview."""
        _prepopulate_catalog()
        deps = _make_deps()
        with respx.mock(assert_all_called=False, assert_all_mocked=False) as router:
            _setup_respx_router(router)
            events = await _collect_events(deps, "create step")

        tool_names = _extract_tool_names(events)
        assert "get_search_overview" in tool_names, (
            f"Discovery phase did not call get_search_overview. Tool calls: {tool_names}"
        )

    @pytest.mark.anyio
    async def test_planning_phase_tool_calls(self) -> None:
        """Planning phase calls create_plan and submit_plan."""
        _prepopulate_catalog()
        deps = _make_deps()
        with respx.mock(assert_all_called=False, assert_all_mocked=False) as router:
            _setup_respx_router(router)
            events = await _collect_events(deps, "create step")

        tool_names = _extract_tool_names(events)
        assert "create_plan" in tool_names, (
            f"Planning phase did not call create_plan. Tool calls: {tool_names}"
        )
        assert "submit_plan" in tool_names, (
            f"Planning phase did not call submit_plan. Tool calls: {tool_names}"
        )

    @pytest.mark.anyio
    async def test_execution_phase_tool_calls(self) -> None:
        """Execution phase calls create_leaf_step."""
        _prepopulate_catalog()
        deps = _make_deps()
        with respx.mock(assert_all_called=False, assert_all_mocked=False) as router:
            _setup_respx_router(router)
            events = await _collect_events(deps, "create step")

        tool_names = _extract_tool_names(events)
        assert "create_leaf_step" in tool_names, (
            f"Execution phase did not call create_leaf_step. Tool calls: {tool_names}"
        )

    @pytest.mark.anyio
    async def test_verification_phase_emits_text(self) -> None:
        """Verification phase produces text (assistant_delta or assistant_message)."""
        _prepopulate_catalog()
        deps = _make_deps()
        with respx.mock(assert_all_called=False, assert_all_mocked=False) as router:
            _setup_respx_router(router)
            events = await _collect_events(deps, "create step")

        text_event_types = {"assistant_delta", "assistant_message"}
        text_events = [e for e in events if e.get("type") in text_event_types]
        assert len(text_events) > 0, "Verification phase produced no text events"


class TestE2EPipelineStructuredHandoff:
    """Verify structured handoff state after pipeline completion."""

    @pytest.mark.anyio
    async def test_discovery_populates_agent_state(self) -> None:
        """After the pipeline, GenesByTaxon is registered as discovered."""
        _prepopulate_catalog()
        deps = _make_deps()
        with respx.mock(assert_all_called=False, assert_all_mocked=False) as router:
            _setup_respx_router(router)
            await _collect_events(deps, "create step")

        assert deps.agent_state.is_search_discovered("GenesByTaxon"), (
            "Discovery did not register GenesByTaxon in agent_state"
        )
        overview = deps.agent_state.get_overview("GenesByTaxon")
        assert overview is not None
        assert overview.search_name == "GenesByTaxon"
        assert overview.record_type == "transcript"

    @pytest.mark.anyio
    async def test_plan_reaches_terminal_status(self) -> None:
        """After the pipeline, the active plan exists and has a terminal status."""
        _prepopulate_catalog()
        deps = _make_deps()
        with respx.mock(assert_all_called=False, assert_all_mocked=False) as router:
            _setup_respx_router(router)
            await _collect_events(deps, "create step")

        plan = deps.agent_state.active_plan
        assert plan is not None, "No active plan after pipeline"
        terminal_statuses = {PlanStatus.COMPLETE, PlanStatus.FAILED}
        assert plan.status in terminal_statuses, (
            f"Plan status is {plan.status}, expected COMPLETE or FAILED"
        )

    @pytest.mark.anyio
    async def test_graph_has_steps(self) -> None:
        """After execution, the strategy graph has at least 1 step."""
        _prepopulate_catalog()
        deps = _make_deps()
        with respx.mock(assert_all_called=False, assert_all_mocked=False) as router:
            _setup_respx_router(router)
            await _collect_events(deps, "create step")

        graph = deps.strategy_session.graph
        assert graph is not None, "No graph in strategy session"
        assert len(graph.steps) >= 1, (
            f"Graph has {len(graph.steps)} steps, expected at least 1"
        )


class TestE2EPipelineFullTraversal:
    """Run the full pipeline once and verify all invariants together."""

    @pytest.mark.anyio
    async def test_full_pipeline_traversal(self) -> None:
        """Full pipeline produces correct events and leaves correct state.

        Single test that exercises all 4 phases end-to-end, verifying event
        ordering, phase tool calls, structured handoff, and graph state.
        """
        _prepopulate_catalog()
        deps = _make_deps()
        with respx.mock(assert_all_called=False, assert_all_mocked=False) as router:
            _setup_respx_router(router)
            events = await _collect_events(deps, "create step")

        # -- Event ordering --
        event_types = [str(e.get("type")) for e in events]
        assert events[-1].get("type") == "message_end", (
            f"Last event is {events[-1].get('type')}, not message_end"
        )
        assert "assistant_message" in event_types
        assert "tool_call_start" in event_types
        assert "tool_call_end" in event_types

        # -- Phase tool calls --
        tool_names = _extract_tool_names(events)
        assert "get_search_overview" in tool_names, "Missing discovery tool call"
        assert "create_plan" in tool_names, "Missing planning tool call"
        assert "submit_plan" in tool_names, "Missing planning submit call"
        assert "create_leaf_step" in tool_names, "Missing execution tool call"

        # -- Tool call pairing --
        start_ids = _extract_ids(events, "tool_call_start")
        end_ids = _extract_ids(events, "tool_call_end")
        for sid in start_ids:
            assert sid in end_ids, f"Unmatched tool_call_start: {sid}"

        # -- Structured handoff --
        assert deps.agent_state.is_search_discovered("GenesByTaxon")
        plan = deps.agent_state.active_plan
        assert plan is not None
        assert plan.status in {PlanStatus.COMPLETE, PlanStatus.FAILED}

        # -- Graph state --
        graph = deps.strategy_session.graph
        assert graph is not None
        assert len(graph.steps) >= 1


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------


def _extract_tool_names(events: list[JSONObject]) -> list[str]:
    """Extract tool names from tool_call_start events."""
    return [
        str(e.get("data", {}).get("name", ""))
        for e in events
        if e.get("type") == "tool_call_start" and isinstance(e.get("data"), dict)
    ]


def _extract_ids(events: list[JSONObject], event_type: str) -> list[str]:
    """Extract IDs from tool_call_start or tool_call_end events."""
    return [
        str(e.get("data", {}).get("id", ""))
        for e in events
        if e.get("type") == event_type and isinstance(e.get("data"), dict)
    ]
