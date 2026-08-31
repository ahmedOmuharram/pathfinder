"""An inner tool's own line becomes the sub-agent step's text.

The summary names an inner call, and no reducer on the main stream holds one,
so the chunk must not travel; the line must.
"""

from __future__ import annotations

from typing import Any

from assistant_core.graph.stream_events import tool_summary_event
from pydantic_ai.messages import (
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.ui.vercel_ai.response_types import DataChunk

from pathfinder.ai.lead.sub_agent_events import _forward_inner_event

_PARENT = "sa_1"
_INNER = "s1"


def _collect() -> tuple[list[dict[str, Any]], Any]:
    captured: list[dict[str, Any]] = []

    def writer(payload: dict[str, Any]) -> None:
        captured.append(payload)

    return captured, writer


def _run(metadata: list[Any]) -> list[dict[str, Any]]:
    captured, writer = _collect()
    inner_calls: dict[str, str] = {}
    _forward_inner_event(
        parent_tool_call_id=_PARENT,
        writer=writer,
        inner_calls=inner_calls,
        event=FunctionToolCallEvent(
            part=ToolCallPart(
                tool_name="search_for_searches",
                args={"query": "heat shock"},
                tool_call_id=_INNER,
            ),
        ),
    )
    _forward_inner_event(
        parent_tool_call_id=_PARENT,
        writer=writer,
        inner_calls=inner_calls,
        event=FunctionToolResultEvent(
            part=ToolReturnPart(
                tool_name="search_for_searches",
                content={"total": 12},
                tool_call_id=_INNER,
                metadata=metadata,
            ),
        ),
    )
    return [payload["chunk"] for payload in captured]


def test_the_inner_line_becomes_the_step_text() -> None:
    chunks = _run(
        [tool_summary_event(tool_call_id=_INNER, summary="12 searches")],
    )

    completed = [
        chunk
        for chunk in chunks
        if chunk["type"] == "data-sub-agent-step"
        and chunk["data"]["state"] == "completed"
    ]
    assert len(completed) == 1
    assert completed[0]["data"]["resultSummary"] == "12 searches"


def test_no_summary_chunk_names_an_inner_call() -> None:
    chunks = _run(
        [tool_summary_event(tool_call_id=_INNER, summary="12 searches")],
    )

    assert [c for c in chunks if c["type"] == "data-tool-summary"] == []


def test_a_figure_beside_the_summary_still_reaches_the_stream() -> None:
    chunks = _run(
        [
            DataChunk(type="data-graph-snapshot", data={"steps": []}),
            tool_summary_event(tool_call_id=_INNER, summary="12 searches"),
        ],
    )

    assert [c["type"] for c in chunks if c["type"].startswith("data-graph")] == [
        "data-graph-snapshot"
    ]


def test_the_json_dump_is_the_fallback_when_the_tool_wrote_no_line() -> None:
    chunks = _run([])

    completed = [
        chunk
        for chunk in chunks
        if chunk["type"] == "data-sub-agent-step"
        and chunk["data"]["state"] == "completed"
    ]
    assert completed[0]["data"]["resultSummary"] == '{"total": 12}'
