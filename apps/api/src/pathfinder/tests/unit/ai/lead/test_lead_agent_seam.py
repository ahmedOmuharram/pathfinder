"""The seam between the turn graph and the agent it runs.

A module-level agent is one agent for the whole process: its tools, its model
and its ``override`` state are shared by every turn. The graph is built with a
factory instead, so the agent belongs to the turn that runs it.
"""

from __future__ import annotations

import asyncio
import inspect
from datetime import UTC, datetime
from uuid import uuid4

from assistant_core.memory.schemas import MemoryValue
from pydantic_ai import RunContext
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage
from sqlalchemy.ext.asyncio import AsyncSession

import pathfinder.ai.graph.lead_node as lead_node_mod
import pathfinder.ai.lead.lead_agent as lead_agent_mod
from pathfinder.ai.agents._instructions import pinned_user_memories
from pathfinder.ai.graph.builder import build_graph
from pathfinder.ai.graph.lead_node import make_lead_node
from pathfinder.ai.graph.runtime import Context
from pathfinder.ai.graph.state import PipelineState
from pathfinder.ai.lead._lead_instructions import LEAD_INSTRUCTIONS
from pathfinder.ai.lead.lead_agent import LEAD_MODEL, build_lead_agent
from pathfinder.ai.lead.sub_agent_tools import LeadDeps
from pathfinder.ai.models.settings import baked_model_id
from pathfinder.domain.strategy.session import StrategySession
from pathfinder.services.research.literature_search import LiteratureSearchService
from pathfinder.services.research.web_search import WebSearchService

LEAD_TOOL_NAMES = frozenset(
    {
        "build_control_set",
        "build_strategy",
        "classify_user_intent",
        "clear_strategy",
        "compare_search_variants",
        "compare_variants_scored",
        "consult_user",
        "edit_strategy",
        "frame_problem",
        "get_live_strategy_state",
        "web_search",
        "literature_search",
        "import_control_ids_from_gene_set",
        "import_control_ids_from_strategy",
        "list_control_sets",
        "read_ledger_section",
        "recover_failed_steps",
        "remember",
        "verify_strategy",
    }
)

PINNED_INSTRUCTIONS = [
    "pinned_user_memories",
    "pinned_user_prompt",
    "pinned_user_intent",
    "pinned_operational_spec",
    "pinned_ledger_summary",
    "pinned_run_budget",
    "pinned_machine_guarantees",
    "pinned_turn_briefing",
]


def test_the_lead_module_owns_no_agent_singleton() -> None:
    assert "lead_agent" not in vars(lead_agent_mod)


def test_the_turn_node_owns_no_agent_singleton() -> None:
    assert "lead_agent" not in vars(lead_node_mod)


def test_each_build_returns_its_own_agent() -> None:
    assert build_lead_agent() is not build_lead_agent()


def test_the_built_agent_carries_every_lead_tool() -> None:
    assert set(build_lead_agent()._function_toolset.tools) == LEAD_TOOL_NAMES


def test_the_consult_and_clear_tools_ask_for_approval() -> None:
    """The two tools the user answers: a design fork, and a deletion."""
    tools = build_lead_agent()._function_toolset.tools
    deferred = sorted(name for name, tool in tools.items() if tool.requires_approval)
    assert deferred == ["clear_strategy", "consult_user"]


def test_the_built_agent_keeps_its_model_and_identity() -> None:
    agent = build_lead_agent()
    assert baked_model_id(agent) == LEAD_MODEL
    assert agent.name == "lead"


def test_the_built_agent_pins_the_same_instructions_in_the_same_order() -> None:
    instructions = build_lead_agent()._instructions
    assert instructions[0] == LEAD_INSTRUCTIONS
    names = [getattr(fn, "__name__", "") for fn in instructions[1:]]
    assert names == PINNED_INSTRUCTIONS


def test_the_graph_is_built_with_an_agent_factory() -> None:
    params = inspect.signature(build_graph).parameters
    assert "build_agent" in params
    assert params["build_agent"].default is inspect.Parameter.empty


def test_the_node_factory_takes_the_agent_factory() -> None:
    assert "build_agent" in inspect.signature(make_lead_node).parameters


def _lead_deps(memories: list[MemoryValue]) -> LeadDeps:
    def _never_factory() -> AsyncSession:
        msg = "the pinned render opened a database session"
        raise AssertionError(msg)

    state = PipelineState(
        conversation_id=uuid4(),
        user_id=uuid4(),
        site_id="plasmodb",
        mode="strategy",
    )
    return LeadDeps(
        state=state,
        intent=None,
        runtime=Context(
            site_id="plasmodb",
            user_id=uuid4(),
            strategy_session=StrategySession(site_id="plasmodb"),
            db_session_factory=_never_factory,
            web_search_service=WebSearchService(),
            literature_search_service=LiteratureSearchService(),
            cancel_event=asyncio.Event(),
        ),
        retrieved_memories=memories,
    )


def test_the_lead_renders_the_memories_its_turn_retrieved() -> None:
    """CLAUDE.md says memories reach the Lead; the render reads its deps."""
    memory = MemoryValue(
        kind="preference",
        name="preferred_dataset",
        summary="Prefers the Su et al. strand-specific dataset",
        content={},
        created_at=datetime.now(UTC),
    )
    ctx = RunContext(deps=_lead_deps([memory]), model=TestModel(), usage=RunUsage())

    rendered = pinned_user_memories(ctx)

    assert rendered is not None
    assert "Prefers the Su et al. strand-specific dataset" in rendered
    assert (
        pinned_user_memories(
            RunContext(deps=_lead_deps([]), model=TestModel(), usage=RunUsage())
        )
        is None
    )
