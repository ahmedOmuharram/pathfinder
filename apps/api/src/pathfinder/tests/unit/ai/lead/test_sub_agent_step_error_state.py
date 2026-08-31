"""The terminal state of a sub-agent tool step.

A retry prompt or a returned ``ERROR: ...`` directive is a failure, a denied
call is a denial, and anything else is a completion.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic_ai.messages import (
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    RetryPromptPart,
    ToolCallPart,
    ToolReturnPart,
)

from pathfinder.ai.capabilities.error_classification import build_error_directive
from pathfinder.ai.lead.sub_agent_events import _forward_inner_event


def _collect() -> tuple[list[dict[str, Any]], Any]:
    captured: list[dict[str, Any]] = []

    def writer(payload: dict[str, Any]) -> None:
        captured.append(payload)

    return captured, writer


def _result_states(captured: list[dict[str, Any]]) -> list[str]:
    return [
        p["chunk"]["data"]["state"]
        for p in captured
        if p["chunk"]["data"].get("resultSummary") is not None
    ]


def _drive_part(
    part: ToolReturnPart | RetryPromptPart,
    tool_name: str = "get_search_overview",
) -> list[str]:
    captured, writer = _collect()
    inner_calls: dict[str, str] = {}
    _forward_inner_event(
        parent_tool_call_id="parent",
        writer=writer,
        inner_calls=inner_calls,
        event=FunctionToolCallEvent(
            part=ToolCallPart(tool_name=tool_name, tool_call_id="c1"),
        ),
    )
    _forward_inner_event(
        parent_tool_call_id="parent",
        writer=writer,
        inner_calls=inner_calls,
        event=FunctionToolResultEvent(part=part),
    )
    return _result_states(captured)


def _drive(
    result_content: object,
    tool_name: str = "get_search_overview",
    outcome: Literal["success", "denied"] = "success",
) -> list[str]:
    return _drive_part(
        ToolReturnPart(
            content=result_content,
            tool_name=tool_name,
            tool_call_id="c1",
            outcome=outcome,
        ),
        tool_name,
    )


def test_returned_error_directive_renders_as_failed() -> None:
    directive = build_error_directive(
        error_type="SEARCH_NOT_FOUND",
        tool_name="get_search_overview",
        tool_args={"search_name": "GenesByRNASeqMadeUp"},
        detail="VEuPathDB service error: HTTP 404",
        next_actions=["Call search_for_searches(...)"],
        do_not="Do not retry with the same search name",
    )
    assert _drive(directive) == ["failed"]


def test_normal_result_still_renders_as_completed() -> None:
    assert _drive(
        {"search_name": "GenesByText", "display_name": "Gene Text Search"}
    ) == ["completed"]


def test_denied_call_renders_as_denied() -> None:
    assert _drive("The tool call was denied.", outcome="denied") == ["denied"]


def test_retry_prompt_renders_as_failed() -> None:
    assert _drive_part(
        RetryPromptPart(
            content="search_name is not a known search",
            tool_name="get_search_overview",
            tool_call_id="c1",
        ),
    ) == ["failed"]
