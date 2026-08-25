"""The repetition guard over PathFinder's own vocabulary.

The mechanism refuses the Nth consecutive identical read-only call and ends
the run if the model makes that call again. These cases drive it with the
tool names the agents really carry.
"""

from __future__ import annotations

from assistant_core.capabilities.repetition_guard import (
    DEFAULT_REPETITION_THRESHOLD,
)

from pathfinder.ai.agents.tool_vocabulary import build_tool_repetition_guard


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

    block = guard.check("get_strategy", {})

    assert block is not None
    assert block.escalated is False
    assert "loop" in block.message.lower()
    assert guard.total_blocked == 1


def test_the_first_block_leaves_the_run_going() -> None:
    guard = build_tool_repetition_guard()
    for _ in range(DEFAULT_REPETITION_THRESHOLD):
        guard.check("get_strategy", {}, tool_call_id="c1")

    assert guard.stopped_call_id == ""


def test_making_the_refused_call_again_ends_the_run() -> None:
    guard = build_tool_repetition_guard()
    for _ in range(DEFAULT_REPETITION_THRESHOLD):
        guard.check("get_strategy", {}, tool_call_id="c1")

    block = guard.check("get_strategy", {}, tool_call_id="c2")

    assert block is not None
    assert block.escalated is True
    assert "stops here" in block.message
    assert guard.stopped_call_id == "c2"


def test_changing_args_resets_counter() -> None:
    guard = build_tool_repetition_guard()
    assert guard.check("get_strategy", {}) is None
    assert guard.check("get_strategy", {"graph_id": "g1"}) is None
    assert guard.check("get_strategy", {"graph_id": "g2"}) is None


def test_interleaved_calls_do_not_block() -> None:
    """Only consecutive identical calls trip the guard."""
    guard = build_tool_repetition_guard()
    assert guard.check("get_strategy", {}) is None
    assert guard.check("search_memory", {"q": "a"}) is None
    assert guard.check("get_strategy", {}) is None
    assert guard.check("search_memory", {"q": "b"}) is None
    assert guard.check("get_strategy", {}) is None


def test_a_state_changing_tool_resets_counter() -> None:
    guard = build_tool_repetition_guard()
    for _ in range(DEFAULT_REPETITION_THRESHOLD - 1):
        guard.check("get_strategy", {})
    assert guard.check("update_leaf_params", {"step_id": "s1"}) is None
    assert guard.check("get_strategy", {}) is None
    assert guard.check("get_strategy", {}) is None


def test_changing_args_on_readonly_resets_counter() -> None:
    guard = build_tool_repetition_guard()
    for _ in range(DEFAULT_REPETITION_THRESHOLD - 1):
        assert guard.check("get_estimated_size", {}) is None
    assert guard.check("get_estimated_size", {"wdk_step_id": 1}) is None
    assert guard.check("get_estimated_size", {"wdk_step_id": 1}) is None
    assert guard.check("get_estimated_size", {"wdk_step_id": 1}) is not None


def test_unclassified_tool_resets_counter() -> None:
    """A tool outside the vocabulary counts as progress."""
    guard = build_tool_repetition_guard()
    guard.check("get_strategy", {})
    guard.check("get_strategy", {})
    assert guard.check("set_criterion", {"criterion_id": "c1"}) is None
    assert guard.check("get_strategy", {}) is None
    assert guard.check("get_strategy", {}) is None
