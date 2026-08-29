"""The seam between the turn graph and the agent it runs.

A module-level agent is one agent for the whole process: its tools, its model
and its ``override`` state are shared by every turn. The graph is built with a
factory instead, so the agent belongs to the turn that runs it.
"""

from __future__ import annotations

import inspect

import pathfinder.ai.graph.lead_node as lead_node_mod
import pathfinder.ai.lead.lead_agent as lead_agent_mod
from pathfinder.ai.graph.builder import build_graph
from pathfinder.ai.graph.lead_node import make_lead_node
from pathfinder.ai.lead._lead_instructions import LEAD_INSTRUCTIONS
from pathfinder.ai.lead.lead_agent import LEAD_MODEL, build_lead_agent
from pathfinder.ai.models.settings import baked_model_id

LEAD_TOOL_NAMES = frozenset(
    {
        "build_control_set",
        "build_strategy",
        "classify_user_intent",
        "compare_search_variants",
        "compare_variants_scored",
        "consult_user",
        "edit_strategy",
        "frame_problem",
        "get_live_strategy_state",
        "import_control_ids_from_gene_set",
        "import_control_ids_from_strategy",
        "list_control_sets",
        "read_ledger_section",
        "recover_failed_steps",
        "verify_strategy",
    }
)

PINNED_INSTRUCTIONS = [
    "pinned_user_prompt",
    "pinned_user_intent",
    "pinned_operational_spec",
    "pinned_ledger_summary",
]


def test_the_lead_module_owns_no_agent_singleton() -> None:
    assert "lead_agent" not in vars(lead_agent_mod)


def test_the_turn_node_owns_no_agent_singleton() -> None:
    assert "lead_agent" not in vars(lead_node_mod)


def test_each_build_returns_its_own_agent() -> None:
    assert build_lead_agent() is not build_lead_agent()


def test_the_built_agent_carries_every_lead_tool() -> None:
    assert set(build_lead_agent()._function_toolset.tools) == LEAD_TOOL_NAMES


def test_only_the_consult_tool_still_asks_for_approval() -> None:
    tools = build_lead_agent()._function_toolset.tools
    deferred = sorted(name for name, tool in tools.items() if tool.requires_approval)
    assert deferred == ["consult_user"]


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
