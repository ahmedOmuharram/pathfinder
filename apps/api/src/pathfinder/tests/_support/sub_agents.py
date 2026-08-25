"""Helpers for tests that read or pin a per-dispatch sub-agent."""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from typing import Any

import pytest
from pydantic_ai import Agent
from pydantic_ai.toolsets.abstract import AbstractToolset
from pydantic_ai.toolsets.function import FunctionToolset
from pydantic_ai.toolsets.wrapper import WrapperToolset

from pathfinder.ai.agents.roles import PhaseRole
from pathfinder.ai.lead import sub_agent_tools


def toolset_tool_names(toolset: AbstractToolset[Any]) -> set[str]:
    """The names a toolset offers, through however many wrappers it carries."""
    while isinstance(toolset, WrapperToolset):
        toolset = toolset.wrapped
    if isinstance(toolset, FunctionToolset):
        return set(toolset.tools)
    return set()


def agent_tool_names(agent: Agent[Any, Any]) -> set[str]:
    """Every tool name the agent can call, across all of its toolsets."""
    return {name for ts in agent.toolsets for name in toolset_tool_names(ts)}


@contextlib.contextmanager
def pinned_sub_agent(
    monkeypatch: pytest.MonkeyPatch,
    role: PhaseRole,
    **overrides: Any,
) -> Iterator[None]:
    """Run every dispatch of ``role`` on one agent, overridden as given.

    A dispatch builds its own agent, so a test that overrides one instance
    pins that instance into the factory map for the duration.
    """
    agent = sub_agent_tools.BUILD_SUB_AGENT_BY_ROLE[role]()
    monkeypatch.setitem(
        sub_agent_tools.BUILD_SUB_AGENT_BY_ROLE,
        role,
        lambda: agent,
    )
    with agent.override(**overrides):
        yield
