from __future__ import annotations

from typing import Any

from pydantic_ai.ui.vercel_ai.response_types import DataChunk, TextStartChunk

from pathfinder.ai.lead.sub_agent_tools import _forward_tool_metadata


def _collect() -> tuple[list[dict[str, Any]], Any]:
    captured: list[dict[str, Any]] = []

    def writer(payload: dict[str, Any]) -> None:
        captured.append(payload)

    return captured, writer


def test_forwards_data_chunks() -> None:
    captured, writer = _collect()
    _forward_tool_metadata(
        writer,
        [DataChunk(type="data-plan-artifact", data={"planId": "p1"})],
    )
    assert len(captured) == 1
    assert captured[0]["chunk"]["type"] == "data-plan-artifact"
    assert captured[0]["chunk"]["data"] == {"planId": "p1"}


def test_drops_non_streamable_chunks() -> None:
    captured, writer = _collect()
    _forward_tool_metadata(writer, [TextStartChunk(id="x")])
    assert captured == []


def test_ignores_non_list_metadata() -> None:
    captured, writer = _collect()
    _forward_tool_metadata(writer, None)
    _forward_tool_metadata(writer, "not a list")
    assert captured == []
