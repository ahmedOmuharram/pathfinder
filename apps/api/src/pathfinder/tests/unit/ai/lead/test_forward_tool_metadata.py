"""An inner tool's metadata splits into the step's line and what the stream shows."""

from __future__ import annotations

from pydantic_ai.ui.vercel_ai.response_types import DataChunk, TextStartChunk

from pathfinder.ai.lead.sub_agent_events import _read_tool_metadata


def test_forwards_data_chunks() -> None:
    read = _read_tool_metadata(
        [DataChunk(type="data-plan-artifact", data={"planId": "p1"})],
    )
    assert len(read.forwarded) == 1
    assert read.forwarded[0].type == "data-plan-artifact"
    assert read.summary is None


def test_drops_non_streamable_chunks() -> None:
    read = _read_tool_metadata([TextStartChunk(id="x")])
    assert read.forwarded == []


def test_ignores_non_list_metadata() -> None:
    assert _read_tool_metadata(None).forwarded == []
    assert _read_tool_metadata("not a list").forwarded == []


def test_a_tool_summary_is_lifted_and_never_forwarded() -> None:
    """The inner call id names no part on the main stream, so the chunk stays out."""
    read = _read_tool_metadata(
        [
            DataChunk(
                type="data-tool-summary",
                data={"toolCallId": "s1", "summary": "12 searches", "status": "ok"},
            ),
            DataChunk(type="data-graph-snapshot", data={"steps": []}),
        ],
    )
    assert read.summary == "12 searches"
    assert [chunk.type for chunk in read.forwarded] == ["data-graph-snapshot"]
