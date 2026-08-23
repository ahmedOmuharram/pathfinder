"""The seam between the guard mechanisms and the tools they watch.

Both guards key on tool names. The names are PathFinder's, so they arrive as
constructor arguments; a guard built with no vocabulary watches nothing rather
than watching another product's tools by accident.
"""

from __future__ import annotations

import assistant_core.capabilities.repetition_guard as repetition_mod
from assistant_core.capabilities.repetition_guard import (
    DEFAULT_REPETITION_THRESHOLD,
    ToolRepetitionGuard,
)
from assistant_core.graph.runtime import AssistantDeps

import pathfinder.ai.capabilities.resilience as resilience_mod
from pathfinder.ai.agents.tool_vocabulary import (
    GRAPH_MODIFYING_TOOLS,
    READ_ONLY_TOOLS,
    SEARCH_LOOKUP_TOOLS,
    build_tool_repetition_guard,
)
from pathfinder.ai.capabilities.resilience import ToolResilience
from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.domain.strategy.session import StrategySession

PRODUCT_NAMES = {
    "READ_ONLY_TOOLS",
    "GRAPH_MODIFYING_TOOLS",
    "SEARCH_LOOKUP_TOOLS",
    "_SEARCH_LOOKUP_TOOLS",
}


def test_the_repetition_guard_module_names_no_product_tool() -> None:
    assert PRODUCT_NAMES & set(vars(repetition_mod)) == set()


def test_the_resilience_module_names_no_product_tool() -> None:
    assert PRODUCT_NAMES & set(vars(resilience_mod)) == set()


def test_a_guard_with_no_vocabulary_watches_nothing() -> None:
    guard = ToolRepetitionGuard()
    for _ in range(DEFAULT_REPETITION_THRESHOLD + 1):
        assert guard.check("get_strategy", {}) is None
    assert guard.total_blocked == 0


def test_a_guard_blocks_the_read_only_tools_it_was_given() -> None:
    guard = ToolRepetitionGuard(read_only_tools=frozenset({"peek"}))
    for _ in range(DEFAULT_REPETITION_THRESHOLD - 1):
        assert guard.check("peek", {}) is None
    assert guard.check("peek", {}) is not None


def test_a_guard_honors_the_threshold_it_was_given() -> None:
    guard = ToolRepetitionGuard(read_only_tools=frozenset({"peek"}), threshold=2)
    assert guard.check("peek", {}) is None
    assert guard.check("peek", {}) is not None


def test_a_guard_resets_on_the_modifying_tools_it_was_given() -> None:
    guard = ToolRepetitionGuard(
        read_only_tools=frozenset({"peek"}),
        graph_modifying_tools=frozenset({"poke"}),
    )
    for _ in range(DEFAULT_REPETITION_THRESHOLD - 1):
        guard.check("peek", {})
    assert guard.check("poke", {}) is None
    assert guard.check("peek", {}) is None


def test_the_product_guard_carries_the_pathfinder_vocabulary() -> None:
    guard = build_tool_repetition_guard()
    assert guard.read_only_tools == READ_ONLY_TOOLS
    assert guard.graph_modifying_tools == GRAPH_MODIFYING_TOOLS
    assert "get_strategy" in guard.read_only_tools
    assert "update_step" in guard.graph_modifying_tools


def test_the_generic_deps_default_to_a_guard_that_watches_nothing() -> None:
    deps = AssistantDeps(site_id="plasmodb")
    assert deps.tool_repetition_guard.read_only_tools == frozenset()


def test_the_product_deps_default_to_the_pathfinder_guard() -> None:
    deps = AgentDeps(
        site_id="plasmodb",
        strategy_session=StrategySession(site_id="plasmodb"),
    )
    assert deps.tool_repetition_guard.read_only_tools == READ_ONLY_TOOLS


def test_resilience_takes_its_search_lookup_tools_as_an_argument() -> None:
    capability = ToolResilience(search_lookup_tools=SEARCH_LOOKUP_TOOLS)
    assert capability.search_lookup_tools == SEARCH_LOOKUP_TOOLS
    assert ToolResilience().search_lookup_tools == frozenset()
