from __future__ import annotations

from pathfinder.ai.capabilities.repetition_guard import (
    REPETITION_THRESHOLD,
    ToolRepetitionGuard,
)


def test_first_call_proceeds() -> None:
    guard = ToolRepetitionGuard()
    assert guard.check("get_strategy", {}) is None


def test_two_consecutive_identical_calls_proceed() -> None:
    guard = ToolRepetitionGuard()
    assert guard.check("get_strategy", {}) is None
    assert guard.check("get_strategy", {}) is None


def test_third_consecutive_identical_call_blocks() -> None:
    guard = ToolRepetitionGuard()
    for _ in range(REPETITION_THRESHOLD - 1):
        assert guard.check("get_strategy", {}) is None
    warning = guard.check("get_strategy", {})
    assert warning is not None
    assert "loop" in warning.lower()
    assert guard.total_blocked == 1


def test_changing_args_resets_counter() -> None:
    guard = ToolRepetitionGuard()
    for _ in range(REPETITION_THRESHOLD - 1):
        assert guard.check("get_strategy", {}) is None
    assert guard.check("get_strategy", {"step": 1}) is None
    assert guard.check("get_strategy", {"step": 1}) is None
    assert guard.check("get_strategy", {"step": 1}) is not None


def test_graph_modifying_tool_resets_counter() -> None:
    guard = ToolRepetitionGuard()
    for _ in range(REPETITION_THRESHOLD - 1):
        guard.check("get_strategy", {})
    assert guard.check("update_step", {"step": 1}) is None
    assert guard.check("get_strategy", {}) is None
    assert guard.check("get_strategy", {}) is None


def test_unclassified_tool_resets_counter() -> None:
    guard = ToolRepetitionGuard()
    for _ in range(REPETITION_THRESHOLD - 1):
        guard.check("get_strategy", {})
    assert guard.check("set_problem_frame", {"frame": "x"}) is None
    assert guard.check("get_strategy", {}) is None
