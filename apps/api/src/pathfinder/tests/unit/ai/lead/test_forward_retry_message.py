"""A sub-agent tool that raises ``ModelRetry`` (or fails output validation)
surfaces a ``RetryPromptPart``. The forwarder must put the REAL retry text
into the ``data-sub-agent-step`` result summary — not a generic
"retry requested" placeholder — so the UI and logs show why the step failed.
"""

from __future__ import annotations

from typing import Any

from pydantic_ai.messages import (
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    RetryPromptPart,
    ToolCallPart,
)

from pathfinder.ai.lead.sub_agent_stream import _forward_inner_event


def _collect() -> tuple[list[dict[str, Any]], Any]:
    captured: list[dict[str, Any]] = []

    def writer(payload: dict[str, Any]) -> None:
        captured.append(payload)

    return captured, writer


def _summaries(captured: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for p in captured:
        data = p["chunk"]["data"]
        if data.get("resultSummary") is not None:
            out.append(str(data["resultSummary"]))
    return out


def test_string_retry_surfaces_real_message() -> None:
    captured, writer = _collect()
    inner_calls: dict[str, str] = {}
    _forward_inner_event(
        parent_tool_call_id="parent",
        writer=writer,
        inner_calls=inner_calls,
        event=FunctionToolCallEvent(
            part=ToolCallPart(tool_name="update_search_decision", tool_call_id="c1"),
        ),
    )
    _forward_inner_event(
        parent_tool_call_id="parent",
        writer=writer,
        inner_calls=inner_calls,
        event=FunctionToolResultEvent(
            part=RetryPromptPart(
                content="Unknown search 'GenesByGOTerm'. Call get_search_overview first.",
                tool_name="update_search_decision",
                tool_call_id="c1",
            ),
        ),
    )
    summaries = _summaries(captured)
    assert any("Unknown search 'GenesByGOTerm'" in s for s in summaries)
    assert all("retry requested" not in s for s in summaries)


def test_structured_validation_retry_is_rendered() -> None:
    captured, writer = _collect()
    inner_calls: dict[str, str] = {}
    _forward_inner_event(
        parent_tool_call_id="parent",
        writer=writer,
        inner_calls=inner_calls,
        event=FunctionToolCallEvent(
            part=ToolCallPart(tool_name="build_plan", tool_call_id="c2"),
        ),
    )
    _forward_inner_event(
        parent_tool_call_id="parent",
        writer=writer,
        inner_calls=inner_calls,
        event=FunctionToolResultEvent(
            part=RetryPromptPart(
                content=[
                    {
                        "type": "missing",
                        "loc": ("steps", 0, "search_name"),
                        "msg": "Field required",
                        "input": {},
                    },
                ],
                tool_name="build_plan",
                tool_call_id="c2",
            ),
        ),
    )
    summaries = _summaries(captured)
    assert summaries  # a failed step was emitted with a summary
    joined = " ".join(summaries)
    assert "retry requested" not in joined
    # The rendered validation text mentions the failing field / reason.
    assert (
        "search_name" in joined or "Field required" in joined or "validation" in joined
    )
