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
    assert "ejected" in warning.lower()
    assert guard.total_blocked == 1
    assert guard.eject_to_discovery is True


def test_spam_count_ignores_args_for_spam_prone_tools() -> None:
    guard = ToolRepetitionGuard()
    assert guard.check("get_strategy", {}) is None
    assert guard.check("get_strategy", {"step": 1}) is None
    warning = guard.check("get_strategy", {"step": 2})
    assert warning is not None
    assert "ejected" in warning.lower()


def test_interleaved_spam_pattern_still_ejects() -> None:
    guard = ToolRepetitionGuard()
    assert guard.check("get_strategy", {}) is None
    assert guard.check("search_memory", {"q": "a"}) is None
    assert guard.check("get_strategy", {}) is None
    assert guard.check("search_memory", {"q": "b"}) is None
    warning = guard.check("get_strategy", {})
    assert warning is not None
    assert "ejected" in warning.lower()


def test_graph_modifying_tool_resets_counter() -> None:
    guard = ToolRepetitionGuard()
    for _ in range(REPETITION_THRESHOLD - 1):
        guard.check("get_strategy", {})
    assert guard.check("update_step", {"step": 1}) is None
    assert guard.check("get_strategy", {}) is None
    assert guard.check("get_strategy", {}) is None


def test_changing_args_on_non_spam_readonly_resets_counter() -> None:
    guard = ToolRepetitionGuard()
    for _ in range(REPETITION_THRESHOLD - 1):
        assert guard.check("get_plan", {}) is None
    assert guard.check("get_plan", {"id": 1}) is None
    assert guard.check("get_plan", {"id": 1}) is None
    assert guard.check("get_plan", {"id": 1}) is not None


def test_unclassified_tool_does_not_clear_spam_counts() -> None:
    guard = ToolRepetitionGuard()
    guard.check("get_strategy", {})
    guard.check("get_strategy", {})
    assert guard.check("set_problem_frame", {"frame": "x"}) is None
    warning = guard.check("get_strategy", {})
    assert warning is not None
    assert "ejected" in warning.lower()
