"""Repetition-guard tests after Stage E.

The auto-eject path (SPAM_PRONE_TOOLS, eject_to_discovery) was deleted
in Stage E because execution is now declarative — read-only spam during
execution can't happen by construction. The remaining behavior: block
the 3rd CONSECUTIVE IDENTICAL read-only call (same name, same args, no
intervening state change) on agents that still go through the LLM
(discovery + planning).
"""

from __future__ import annotations

from pathfinder.ai.agents.tool_vocabulary import build_tool_repetition_guard
from pathfinder.assistant_core.capabilities.repetition_guard import (
    DEFAULT_REPETITION_THRESHOLD,
)


def test_first_call_proceeds() -> None:
    guard = build_tool_repetition_guard()
    assert guard.check("get_strategy", {}) is None


def test_two_consecutive_identical_calls_proceed() -> None:
    guard = build_tool_repetition_guard()
    assert guard.check("get_strategy", {}) is None
    assert guard.check("get_strategy", {}) is None


def test_third_consecutive_identical_call_blocks() -> None:
    guard = build_tool_repetition_guard()
    for _ in range(DEFAULT_REPETITION_THRESHOLD - 1):
        assert guard.check("get_strategy", {}) is None
    warning = guard.check("get_strategy", {})
    assert warning is not None
    assert "loop" in warning.lower()
    assert guard.total_blocked == 1


def test_changing_args_resets_counter() -> None:
    guard = build_tool_repetition_guard()
    assert guard.check("get_strategy", {}) is None
    assert guard.check("get_strategy", {"step": 1}) is None
    assert guard.check("get_strategy", {"step": 2}) is None


def test_interleaved_calls_do_not_block() -> None:
    """Without the spam-eject path, alternating calls do not trip the
    guard — only consecutive identical calls do."""
    guard = build_tool_repetition_guard()
    assert guard.check("get_strategy", {}) is None
    assert guard.check("search_memory", {"q": "a"}) is None
    assert guard.check("get_strategy", {}) is None
    assert guard.check("search_memory", {"q": "b"}) is None
    assert guard.check("get_strategy", {}) is None


def test_graph_modifying_tool_resets_counter() -> None:
    guard = build_tool_repetition_guard()
    for _ in range(DEFAULT_REPETITION_THRESHOLD - 1):
        guard.check("get_strategy", {})
    assert guard.check("update_step", {"step": 1}) is None
    assert guard.check("get_strategy", {}) is None
    assert guard.check("get_strategy", {}) is None


def test_changing_args_on_readonly_resets_counter() -> None:
    guard = build_tool_repetition_guard()
    for _ in range(DEFAULT_REPETITION_THRESHOLD - 1):
        assert guard.check("get_plan", {}) is None
    assert guard.check("get_plan", {"id": 1}) is None
    assert guard.check("get_plan", {"id": 1}) is None
    assert guard.check("get_plan", {"id": 1}) is not None


def test_unclassified_tool_resets_counter() -> None:
    """Unknown tools (neither read-only nor graph-modifying) reset the
    counter — they're considered state-changing by default."""
    guard = build_tool_repetition_guard()
    guard.check("get_strategy", {})
    guard.check("get_strategy", {})
    assert guard.check("set_problem_frame", {"frame": "x"}) is None
    assert guard.check("get_strategy", {}) is None
    assert guard.check("get_strategy", {}) is None
