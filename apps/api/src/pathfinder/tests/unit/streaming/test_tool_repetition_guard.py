"""Tests for the tool repetition guard (anti-thrash circuit breaker)."""

from pathfinder.services.chat.tool_repetition_guard import (
    ToolRepetitionGuard,
    _args_fingerprint,
)

# === Basic behavior ===


def test_first_call_always_allowed() -> None:
    """First call to any read-only tool is never blocked."""
    guard = ToolRepetitionGuard()
    assert guard.check("get_strategy", {"summary_only": True}) is None


def test_second_identical_call_allowed() -> None:
    """Two identical calls are under threshold."""
    guard = ToolRepetitionGuard()
    guard.check("get_strategy", {"summary_only": True})
    assert guard.check("get_strategy", {"summary_only": True}) is None


def test_third_identical_call_blocked() -> None:
    """Three consecutive identical read-only calls trigger the guard."""
    guard = ToolRepetitionGuard()
    guard.check("get_strategy", {"summary_only": True})
    guard.check("get_strategy", {"summary_only": True})
    result = guard.check("get_strategy", {"summary_only": True})
    assert result is not None
    assert "loop" in result.lower()


# === Reset behavior ===


def test_modifying_tool_resets_counter() -> None:
    """A graph-modifying tool call resets the consecutive counter."""
    guard = ToolRepetitionGuard()
    guard.check("get_strategy", {"summary_only": True})
    guard.check("get_strategy", {"summary_only": True})
    # Modify resets
    guard.check("create_leaf_step", {"search_name": "GenesByGoTerm"})
    # Now two more reads should be fine
    assert guard.check("get_strategy", {"summary_only": True}) is None
    assert guard.check("get_strategy", {"summary_only": True}) is None


def test_record_modifying_call_resets() -> None:
    """record_modifying_call explicitly resets even without check()."""
    guard = ToolRepetitionGuard()
    guard.check("get_strategy", {"summary_only": True})
    guard.check("get_strategy", {"summary_only": True})
    guard.record_modifying_call("update_step")
    assert guard.check("get_strategy", {"summary_only": True}) is None
    assert guard.check("get_strategy", {"summary_only": True}) is None


def test_different_read_tool_resets_counter() -> None:
    """Switching to a different read-only tool resets the counter."""
    guard = ToolRepetitionGuard()
    guard.check("get_strategy", {"summary_only": True})
    guard.check("get_strategy", {"summary_only": True})
    # Different tool resets
    guard.check("get_plan", {})
    guard.check("get_plan", {})
    # Back to get_strategy starts fresh
    assert guard.check("get_strategy", {"summary_only": True}) is None


def test_same_tool_different_args_resets_counter() -> None:
    """Same tool with different arguments is a new sequence."""
    guard = ToolRepetitionGuard()
    guard.check("get_strategy", {"summary_only": True})
    guard.check("get_strategy", {"summary_only": True})
    # Different args resets
    guard.check("get_strategy", {"summary_only": False})
    guard.check("get_strategy", {"summary_only": False})
    # 3rd call with same args -> blocked
    assert guard.check("get_strategy", {"summary_only": False}) is not None


# === Interleaved patterns ===


def test_interleaved_read_modify_read_allows_all() -> None:
    """get_strategy -> create_step -> get_strategy is allowed."""
    guard = ToolRepetitionGuard()
    assert guard.check("get_strategy", {}) is None
    assert guard.check("create_leaf_step", {"search_name": "x"}) is None
    assert guard.check("get_strategy", {}) is None


def test_read_read_modify_read_read_allows() -> None:
    """Two reads, one modify, two reads -- all allowed."""
    guard = ToolRepetitionGuard()
    assert guard.check("get_strategy", {}) is None
    assert guard.check("get_strategy", {}) is None
    assert guard.check("update_step", {}) is None  # resets
    assert guard.check("get_strategy", {}) is None
    assert guard.check("get_strategy", {}) is None


def test_three_reads_then_modify_then_three_reads() -> None:
    """First 3 reads: 3rd blocked. Modify resets. Next 3 reads: 3rd blocked again."""
    guard = ToolRepetitionGuard()
    guard.check("get_plan", {})
    guard.check("get_plan", {})
    assert guard.check("get_plan", {}) is not None  # blocked
    guard.check("create_leaf_step", {})  # resets
    guard.check("get_plan", {})
    guard.check("get_plan", {})
    assert guard.check("get_plan", {}) is not None  # blocked again


# === Edge cases ===


def test_non_classified_tool_resets_counter() -> None:
    """Tools not in READ_ONLY or GRAPH_MODIFYING reset the counter."""
    guard = ToolRepetitionGuard()
    guard.check("get_strategy", {})
    guard.check("get_strategy", {})
    guard.check("some_unknown_tool", {})  # resets
    assert guard.check("get_strategy", {}) is None


def test_guard_tracks_total_blocked() -> None:
    """total_blocked property counts how many times the guard fired."""
    guard = ToolRepetitionGuard()
    assert guard.total_blocked == 0
    for _ in range(5):
        guard.check("get_strategy", {})
    assert guard.total_blocked == 3  # fired on calls 3, 4, 5


def test_args_fingerprint_stability() -> None:
    """Same args produce the same fingerprint regardless of dict ordering."""
    a = _args_fingerprint({"b": 2, "a": 1})
    b = _args_fingerprint({"a": 1, "b": 2})
    assert a == b


def test_none_args_handled() -> None:
    """Tool called with None args doesn't crash the guard."""
    guard = ToolRepetitionGuard()
    assert guard.check("get_strategy", None) is None
    assert guard.check("get_strategy", None) is None
    assert guard.check("get_strategy", None) is not None
