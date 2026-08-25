"""The seam between generic pinned instructions and PathFinder's renderers.

An assistant pins what it knows about the user and its own notes; a strategy
builder also pins the graph, the ledger, the spec and the searches it found.
Each agent names the renderers it wants, so the generic module stays free of
strategy vocabulary.
"""

from __future__ import annotations

from collections.abc import Callable
from types import ModuleType
from typing import Any

import pytest

import pathfinder.ai.agents._instructions as generic_mod
import pathfinder.ai.agents.strategy_instructions as strategy_mod
from pathfinder.ai.agents.execution import build_execution_agent
from pathfinder.ai.agents.frame import build_frame_agent
from pathfinder.ai.agents.verification import build_verification_agent

STRATEGY_RENDERERS = {
    "base_system_prompt",
    "pinned_frame_workspace",
    "pinned_graph_state",
    "pinned_ledger",
    "pinned_discovered_searches",
}

GENERIC_RENDERERS = {
    "pinned_user_memories",
    "pinned_scratchpad",
}

INSTRUCTION_ORDER = {
    "frame": [
        "base_system_prompt",
        "pinned_user_memories",
        "pinned_scratchpad",
        "pinned_frame_workspace",
    ],
    "execution": [
        "base_system_prompt",
        "pinned_graph_state",
        "pinned_user_memories",
        "pinned_scratchpad",
        "pinned_ledger",
        "pinned_discovered_searches",
    ],
    "verification": [
        "base_system_prompt",
        "pinned_graph_state",
        "pinned_user_memories",
        "pinned_scratchpad",
        "pinned_ledger",
        "pinned_discovered_searches",
    ],
}

BUILDERS: dict[str, Callable[[], Any]] = {
    "frame": build_frame_agent,
    "execution": build_execution_agent,
    "verification": build_verification_agent,
}


def _named(module: ModuleType) -> set[str]:
    return {
        name
        for name, value in vars(module).items()
        if callable(value) and getattr(value, "__module__", "") == module.__name__
    }


def test_the_generic_module_renders_no_strategy_content() -> None:
    assert _named(generic_mod) == GENERIC_RENDERERS


def test_the_product_module_owns_every_strategy_renderer() -> None:
    assert _named(strategy_mod) >= STRATEGY_RENDERERS


@pytest.mark.parametrize("role", sorted(BUILDERS))
def test_each_agent_pins_its_renderers_in_the_same_order(role: str) -> None:
    names = [
        item if isinstance(item, str) else item.__name__
        for item in BUILDERS[role]()._instructions
    ]
    assert names[1:] == INSTRUCTION_ORDER[role]
