from __future__ import annotations

import pytest
from pydantic_ai import Agent
from pydantic_ai.toolsets.function import FunctionToolset

from pathfinder.ai.agents.discovery import discovery_agent
from pathfinder.ai.agents.execution import execution_agent
from pathfinder.ai.agents.planning import planning_agent
from pathfinder.ai.agents.scoping import scoping_agent
from pathfinder.ai.agents.verification import verification_agent
from pathfinder.ai.scratchpad.tools import build_scratchpad_toolset

_SCRATCHPAD_TOOL_NAMES = (
    "note",
    "list_notes",
    "search_notes",
    "read_note",
    "update_note",
    "delete_note",
    "pin_note",
    "unpin_note",
    "promote_to_memory",
)


def test_scratchpad_toolset_lists_all_tools() -> None:
    """``build_scratchpad_toolset`` is the single source of scratchpad tools."""
    ts = build_scratchpad_toolset()
    names = set(ts.tools.keys())
    for required in _SCRATCHPAD_TOOL_NAMES:
        assert required in names, f"{required} missing from build_scratchpad_toolset"


def _caller_toolsets(
    agent: Agent[object, object],
) -> list[FunctionToolset[object]]:
    """Return only the toolsets passed to the agent at construction time.

    pydantic-ai prepends a synthetic ``_AgentFunctionToolset`` (subclass of
    ``FunctionToolset``) that wraps the output schema; we want the two
    caller-provided toolsets (phase tools + scratchpad tools), so filter by
    exact type.
    """
    return [ts for ts in agent.toolsets if type(ts) is FunctionToolset]


def _flat_tool_names_from_agent(agent: Agent[object, object]) -> set[str]:
    found: set[str] = set()
    for ts in _caller_toolsets(agent):
        found.update(ts.tools.keys())
    return found


@pytest.mark.parametrize(
    "agent",
    [scoping_agent, discovery_agent, planning_agent, execution_agent, verification_agent],
    ids=["scoping", "discovery", "planning", "execution", "verification"],
)
def test_phase_agent_exposes_scratchpad_tools(agent: Agent[object, object]) -> None:
    """Each phase agent composes the scratchpad toolset alongside its phase tools."""
    names = _flat_tool_names_from_agent(agent)
    for required in _SCRATCHPAD_TOOL_NAMES:
        assert required in names, (
            f"{required} missing from {agent.name!r} agent toolsets"
        )


@pytest.mark.parametrize(
    "agent",
    [scoping_agent, discovery_agent, planning_agent, execution_agent, verification_agent],
    ids=["scoping", "discovery", "planning", "execution", "verification"],
)
def test_phase_toolset_does_not_embed_scratchpad(
    agent: Agent[object, object],
) -> None:
    """Scratchpad tools come from the scratchpad toolset only — not duplicated
    into the phase toolset. Guards against DRY-violating re-imports.
    """
    phase_toolsets = _caller_toolsets(agent)
    # There must be exactly 2 caller-provided toolsets: the phase-specific
    # one and the scratchpad one. The scratchpad one owns every scratchpad
    # tool.
    assert len(phase_toolsets) == 2, (
        f"{agent.name!r} has {len(phase_toolsets)} caller FunctionToolsets; "
        "expected 2"
    )
    owners: dict[str, int] = dict.fromkeys(_SCRATCHPAD_TOOL_NAMES, 0)
    for ts in phase_toolsets:
        for name in ts.tools:
            if name in owners:
                owners[name] += 1
    for name, count in owners.items():
        assert count == 1, (
            f"{name} is defined {count} times across {agent.name!r}'s toolsets; "
            f"expected exactly 1 (scratchpad-only)"
        )
