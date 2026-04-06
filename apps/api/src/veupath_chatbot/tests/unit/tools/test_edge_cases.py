"""Edge-case tests across multiple tools and domain objects.

Covers empty/degenerate inputs, immutability contracts, abort from initial
state, and event emission without a queue.
"""

import asyncio
import dataclasses
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from veupath_chatbot.ai.agents.state import AgentToolState, SearchOverview
from veupath_chatbot.ai.orchestration.deps import AgentDeps
from veupath_chatbot.ai.orchestration.phase_results import DiscoveryResult
from veupath_chatbot.ai.tools.standalone._validation_helpers import StepOkResponse
from veupath_chatbot.ai.tools.standalone.strategy_build import (
    combine_steps,
    create_leaf_step,
)
from veupath_chatbot.domain.strategy.ast import PlanStepNode
from veupath_chatbot.domain.strategy.ops import CombineOp
from veupath_chatbot.domain.strategy.plan import (
    PlannedStep,
    PlanStatus,
    StepStatus,
    StepType,
    StrategyPlan,
)
from veupath_chatbot.domain.strategy.session import StrategyGraph, StrategySession
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.strategies.step_creation import StepCreationResult

# ── Helpers ────────────────────────────────────────────────────────────────


def _make_session(site_id: str = "plasmodb") -> StrategySession:
    session = StrategySession(site_id=site_id)
    graph = session.create_graph("Edge Case Strategy")
    graph.record_type = "transcript"
    return session


def _make_deps(
    session: StrategySession,
    agent_state: AgentToolState | None = None,
) -> AgentDeps:
    return AgentDeps(
        site_id=session.site_id,
        strategy_session=session,
        agent_state=agent_state or AgentToolState(),
    )


def _make_ctx(deps: AgentDeps) -> MagicMock:
    ctx = MagicMock()
    ctx.deps = deps
    return ctx


def _register_search(state: AgentToolState, search_name: str) -> None:
    state.register_search(
        search_name,
        SearchOverview(
            search_name=search_name,
            display_name=f"{search_name} Display",
            record_type="transcript",
            description=f"Test search {search_name}",
            parameter_names=["organism"],
            required_params=["organism"],
        ),
    )


# ── test_create_leaf_step_with_empty_parameters ───────────────────────────


@pytest.mark.anyio
@patch("veupath_chatbot.ai.tools.standalone.strategy_build.create_step", new_callable=AsyncMock)
async def test_create_leaf_step_with_empty_parameters(
    mock_create_step: AsyncMock,
) -> None:
    """An empty dict for parameters should still produce a valid step."""
    session = _make_session()
    state = AgentToolState()
    _register_search(state, "GenesByTaxon")
    deps = _make_deps(session, state)
    ctx = _make_ctx(deps)

    graph = session.get_graph(None)
    assert graph is not None

    created_step = PlanStepNode(
        search_name="GenesByTaxon",
        display_name="Genes by Taxon",
        parameters={},
    )
    graph.add_step(created_step)

    mock_create_step.return_value = StepCreationResult(
        step=created_step,
        step_id=created_step.id,
        error=None,
    )

    result = await create_leaf_step(
        ctx,
        search_name="GenesByTaxon",
        parameters={},
        display_name="Genes by Taxon",
    )

    assert isinstance(result, StepOkResponse)
    assert result.ok is True
    assert result.step.search_name == "GenesByTaxon"


# ── test_combine_steps_with_same_step_twice ───────────────────────────────


@pytest.mark.anyio
@patch("veupath_chatbot.ai.tools.standalone.strategy_build.create_step", new_callable=AsyncMock)
async def test_combine_steps_with_same_step_twice(
    mock_create_step: AsyncMock,
) -> None:
    """Combining a step with itself should be accepted by combine_steps.

    The tool itself does not prevent self-combination — that is a validation
    concern at the WDK layer. The tool should pass both IDs through.
    """
    session = _make_session()
    state = AgentToolState()
    deps = _make_deps(session, state)
    ctx = _make_ctx(deps)

    graph = session.get_graph(None)
    assert graph is not None

    step = PlanStepNode(search_name="GenesByTaxon", display_name="Step A")
    graph.add_step(step)

    combined = PlanStepNode(
        search_name="__combine__",
        display_name="Self-union",
        primary_input=step,
        secondary_input=step,
        operator=CombineOp.UNION,
    )
    graph.add_step(combined)

    mock_create_step.return_value = StepCreationResult(
        step=combined,
        step_id=combined.id,
        error=None,
    )

    result = await combine_steps(
        ctx,
        step_a_id=step.id,
        step_b_id=step.id,
        operator="UNION",
    )

    # The tool accepted both IDs being the same.
    assert isinstance(result, StepOkResponse)
    assert result.ok is True


# ── test_get_search_overview_registers_in_agent_state ─────────────────────


def test_get_search_overview_registers_in_agent_state() -> None:
    """After register_search, agent_state should report the search as discovered
    and return the correct overview.
    """
    state = AgentToolState()

    assert not state.is_search_discovered("GenesByTaxon")

    overview = SearchOverview(
        search_name="GenesByTaxon",
        display_name="Genes by Taxon",
        record_type="transcript",
        description="Find genes by organism taxonomy",
        parameter_names=["organism", "min_expr"],
        required_params=["organism"],
    )
    state.register_search("GenesByTaxon", overview)

    assert state.is_search_discovered("GenesByTaxon")
    stored = state.get_overview("GenesByTaxon")
    assert stored is not None
    assert stored.search_name == "GenesByTaxon"
    assert stored.display_name == "Genes by Taxon"
    assert stored.record_type == "transcript"
    assert stored.required_params == ["organism"]
    assert stored.parameter_names == ["organism", "min_expr"]


# ── test_pipeline_abort_from_initial_state ────────────────────────────────


def test_pipeline_abort_from_initial_state() -> None:
    """Aborting from a pristine state (no plan, no graph) should not crash."""
    state = AgentToolState()

    assert state.active_plan is None
    assert len(state.discovered_searches) == 0
    assert len(state.plan_history) == 0

    # clear() should be a no-op on an empty state.
    state.clear()

    assert state.active_plan is None
    assert len(state.discovered_searches) == 0


# ── test_agent_deps_emit_event_without_queue ──────────────────────────────


def test_agent_deps_emit_event_without_queue() -> None:
    """Calling emit_event when event_queue is None should silently no-op."""
    deps = AgentDeps(site_id="plasmodb")
    assert deps.event_queue is None

    # This must NOT raise.
    deps.emit_event({"type": "test", "data": {}})


def test_agent_deps_emit_event_with_queue() -> None:
    """Calling emit_event with a queue should enqueue the event."""
    deps = AgentDeps(site_id="plasmodb")
    queue: asyncio.Queue[JSONObject] = asyncio.Queue()
    deps.event_queue = queue

    event: JSONObject = {"type": "test_event", "data": {"foo": "bar"}}
    deps.emit_event(event)

    assert not queue.empty()
    queued = queue.get_nowait()
    assert queued["type"] == "test_event"
    data = cast("JSONObject", queued["data"])
    assert data["foo"] == "bar"


# ── test_discovery_result_is_frozen ───────────────────────────────────────


def test_discovery_result_is_frozen() -> None:
    """DiscoveryResult is a frozen dataclass — attribute assignment must fail."""
    result = DiscoveryResult(
        discovered_searches={
            "GenesByTaxon": SearchOverview(
                search_name="GenesByTaxon",
                display_name="Genes by Taxon",
                record_type="transcript",
                description="desc",
                parameter_names=["organism"],
                required_params=["organism"],
            )
        },
        research_notes="Found genes",
        intent_summary="User wants malaria genes",
    )

    with pytest.raises(dataclasses.FrozenInstanceError):
        result.research_notes = "mutated"  # type: ignore[misc]

    with pytest.raises(dataclasses.FrozenInstanceError):
        result.intent_summary = "mutated"  # type: ignore[misc]


# ── test_strategy_plan_status_transitions ─────────────────────────────────


def test_strategy_plan_status_transitions() -> None:
    """StrategyPlan.status defaults to DRAFT and can be set to other values."""
    step = PlannedStep(
        id="s1",
        search_name="GenesByTaxon",
        display_name="Test",
        step_type=StepType.LEAF,
        status=StepStatus.READY,
    )
    plan = StrategyPlan(
        title="Test",
        description="desc",
        rationale="rat",
        steps=[step],
        connections=[],
    )

    assert plan.status == PlanStatus.DRAFT

    plan.status = PlanStatus.PRESENTED
    assert plan.status == PlanStatus.PRESENTED

    plan.status = PlanStatus.APPROVED
    assert plan.status == PlanStatus.APPROVED

    plan.status = PlanStatus.EXECUTING
    assert plan.status == PlanStatus.EXECUTING

    plan.status = PlanStatus.COMPLETE
    assert plan.status == PlanStatus.COMPLETE


# ── test_agent_state_set_plan_archives_previous ───────────────────────────


def test_agent_state_set_plan_archives_previous() -> None:
    """Setting a new plan should archive the old one in plan_history."""
    state = AgentToolState()

    step = PlannedStep(
        id="s1",
        search_name="GenesByTaxon",
        display_name="Step 1",
        step_type=StepType.LEAF,
        status=StepStatus.READY,
    )

    plan_1 = StrategyPlan(
        title="Plan 1",
        description="d1",
        rationale="r1",
        steps=[step],
        connections=[],
    )
    plan_2 = StrategyPlan(
        title="Plan 2",
        description="d2",
        rationale="r2",
        steps=[step],
        connections=[],
    )

    state.set_plan(plan_1)
    assert state.active_plan is plan_1
    assert len(state.plan_history) == 0

    state.set_plan(plan_2)
    assert state.active_plan is plan_2
    assert len(state.plan_history) == 1
    assert state.plan_history[0] is plan_1


# ── test_strategy_session_single_graph_model ──────────────────────────────


def test_strategy_session_single_graph_model() -> None:
    """Creating a second graph reuses the existing one, updating the name."""
    session = StrategySession(site_id="plasmodb")

    graph1 = session.create_graph("First")
    graph_id_1 = graph1.id

    graph2 = session.create_graph("Second")

    # Same graph is returned, not a new one.
    assert graph2.id == graph_id_1
    assert graph2.name == "Second"


# ── test_graph_add_step_updates_roots ─────────────────────────────────────


def test_graph_add_step_updates_roots() -> None:
    """Adding a step should update the graph's roots set correctly."""
    graph = StrategyGraph(graph_id="g1", name="Test", site_id="plasmodb")

    leaf = PlanStepNode(search_name="GenesByTaxon", display_name="Leaf")
    graph.add_step(leaf)

    assert leaf.id in graph.roots
    assert graph.last_step_id == leaf.id
