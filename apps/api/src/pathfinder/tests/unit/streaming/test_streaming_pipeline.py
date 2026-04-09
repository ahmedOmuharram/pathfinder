"""Tests for streaming pipeline utilities: event emission, usage merging,
tool-call arg parsing, tag stripper edge cases, and TurnCounters.

NOTE: allowed_tools_for_step and dependency ordering are tested in
test_execution_agent.py — not duplicated here.
"""

import asyncio
from typing import cast

import pytest
from pydantic_ai.usage import RunUsage

from pathfinder.platform.types import JSONObject
from pathfinder.services.chat.streaming.events import (
    emit_delta,
    emit_thoughts,
    parse_tool_call_args,
)
from pathfinder.services.chat.streaming.node_streaming import (
    TurnCounters,
    merge_usage,
)
from pathfinder.services.chat.streaming.tag_stripper import StreamingTagStripper

# ── Helpers ────────────────────────────────────────────────────────────────


def _drain_queue(queue: asyncio.Queue[JSONObject]) -> list[JSONObject]:
    """Synchronously drain all items from a queue."""
    items: list[JSONObject] = []
    while not queue.empty():
        items.append(queue.get_nowait())
    return items


# ── emit_delta / emit_thoughts ──────────────────────────────────────────


@pytest.mark.asyncio
async def testemit_delta_puts_correct_event_type() -> None:
    queue: asyncio.Queue[JSONObject] = asyncio.Queue()
    await emit_delta(queue, "msg-1", "Hello world")

    events = _drain_queue(queue)
    assert len(events) == 1
    assert events[0]["type"] == "assistant_delta"
    data = cast("JSONObject", events[0]["data"])
    assert data["delta"] == "Hello world"
    assert data["messageId"] == "msg-1"


@pytest.mark.asyncio
async def testemit_thoughts_puts_multiple_events() -> None:
    queue: asyncio.Queue[JSONObject] = asyncio.Queue()
    await emit_thoughts(queue, ["thought-A", "thought-B"])

    events = _drain_queue(queue)
    assert len(events) == 2
    assert events[0]["type"] == "planning_thought"
    data0 = cast("JSONObject", events[0]["data"])
    data1 = cast("JSONObject", events[1]["data"])
    assert data0["thought"] == "thought-A"
    assert data1["thought"] == "thought-B"


@pytest.mark.asyncio
async def testemit_thoughts_no_events_for_empty_list() -> None:
    queue: asyncio.Queue[JSONObject] = asyncio.Queue()
    await emit_thoughts(queue, [])

    assert queue.empty()


# ── merge_usage ──────────────────────────────────────────────────────────


def testmerge_usage_accumulates_tokens() -> None:
    """merge_usage should fold Usage into running counters."""
    counters = TurnCounters()
    usage1 = RunUsage(input_tokens=100, output_tokens=50, cache_read_tokens=10, requests=1)
    usage2 = RunUsage(input_tokens=200, output_tokens=75, cache_read_tokens=20, requests=2)

    merge_usage(counters, usage1)
    merge_usage(counters, usage2)

    assert counters.input_tokens == 300
    assert counters.output_tokens == 125
    assert counters.cache_read_tokens == 30
    assert counters.llm_call_count == 3


def testmerge_usage_handles_none_tokens() -> None:
    counters = TurnCounters()
    usage = RunUsage()  # All None

    merge_usage(counters, usage)

    assert counters.input_tokens == 0
    assert counters.output_tokens == 0
    assert counters.cache_read_tokens == 0


# ── parse_tool_call_args ──────────────────────────────────────────────────


def testparse_tool_call_args_dict() -> None:
    result = parse_tool_call_args({"key": "value"})
    assert result == {"key": "value"}


def testparse_tool_call_args_json_string() -> None:
    result = parse_tool_call_args('{"a": 1}')
    assert result == {"a": 1}


def testparse_tool_call_args_invalid_json_string() -> None:
    result = parse_tool_call_args("not json")
    assert result == {}


def testparse_tool_call_args_json_array_string_returns_empty() -> None:
    """A JSON array string should return an empty dict, not the array."""
    result = parse_tool_call_args("[1, 2, 3]")
    assert result == {}


def testparse_tool_call_args_none() -> None:
    result = parse_tool_call_args(None)
    assert result == {}


# ── StreamingTagStripper edge cases ──────────────────────────────────────


def test_tag_stripper_only_whitespace_inside_tag() -> None:
    """Whitespace-only content inside a tag should not produce a thought."""
    stripper = StreamingTagStripper()

    clean, thoughts = stripper.feed("<plan-thinking>   \n  </plan-thinking>ok")
    remaining = stripper.flush()

    assert thoughts == []
    assert "ok" in (clean + remaining)


def test_tag_stripper_reset_state_on_flush() -> None:
    """After flush, the stripper should be in a clean initial state."""
    stripper = StreamingTagStripper()

    stripper.feed("<plan-thinking>thinking")
    stripper.flush()

    # After flush, _inside_tag should be False and buffer empty
    assert stripper._buffer == ""
    assert stripper._inside_tag is False

    # New feed should work without leftover state
    clean, thoughts = stripper.feed("fresh text")
    remaining2 = stripper.flush()
    assert (clean + remaining2) == "fresh text"
    assert thoughts == []


def test_tag_stripper_special_characters_in_thought() -> None:
    """Thought content with special characters (quotes, angles, newlines)."""
    stripper = StreamingTagStripper()

    content = '<plan-thinking>Look at <gene> "PF3D7_0100100" & analyze\nit</plan-thinking>'
    _clean, thoughts = stripper.feed(content)
    stripper.flush()

    assert len(thoughts) == 1
    assert '"PF3D7_0100100"' in thoughts[0]
    assert "& analyze" in thoughts[0]


# ── TurnCounters ─────────────────────────────────────────────────────────


def test_turn_counters_initial_state() -> None:
    counters = TurnCounters()

    assert counters.saw_assistant_message is False
    assert counters.input_tokens == 0
    assert counters.output_tokens == 0
    assert counters.cache_read_tokens == 0
    assert counters.tool_call_count == 0
    assert counters.llm_call_count == 0
    assert counters.accumulated_text_parts == []


def test_turn_counters_accumulated_text_parts() -> None:
    counters = TurnCounters()

    counters.accumulated_text_parts.append("Part 1")
    counters.accumulated_text_parts.append("Part 2")

    assert len(counters.accumulated_text_parts) == 2
    assert "\n\n".join(counters.accumulated_text_parts) == "Part 1\n\nPart 2"
