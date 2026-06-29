"""The deterministic mock's Lead routing: the FRAME→BUILD→VERIFY build journey
plus the consult / variant / attachment branches. These drive the e2e chat
flows, so a regression here silently reds the whole browser suite."""

from __future__ import annotations

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from pathfinder.ai.models import mock


def _user(text: str) -> ModelRequest:
    return ModelRequest(parts=[UserPromptPart(content=text)])


def _names(seq: list[ToolCallPart]) -> list[str]:
    return [c.tool_name for c in seq]


def test_build_journey_frames_builds_verifies() -> None:
    msgs: list[ModelMessage] = [_user("...3d7...interpro...")]
    assert _names(mock._lead_sequence(msgs)) == [
        "frame_problem",
        "build_strategy",
        "verify_strategy",
        "final_result",
    ]


def test_consult_marker_pauses_on_consult_user() -> None:
    msgs: list[ModelMessage] = [_user("Consult me before planning this strategy.")]
    assert _names(mock._lead_sequence(msgs)) == ["consult_user"]


def test_consult_resume_runs_the_build_journey() -> None:
    msgs: list[ModelMessage] = [
        _user("Consult me before planning this strategy."),
        ModelResponse(
            parts=[ToolCallPart(tool_name="consult_user", args={}, tool_call_id="c1")]
        ),
        ModelRequest(
            parts=[
                ToolReturnPart(
                    tool_name="consult_user", content="answered", tool_call_id="c1"
                ),
                UserPromptPart(content="The user answered your questions: ..."),
            ]
        ),
    ]
    assert _names(mock._lead_sequence(msgs)) == [
        "frame_problem",
        "build_strategy",
        "verify_strategy",
        "final_result",
    ]


def test_variant_marker_compares_variants() -> None:
    msgs: list[ModelMessage] = [_user("Compare two search variants for kinases.")]
    assert _names(mock._lead_sequence(msgs)) == [
        "compare_search_variants",
        "final_result",
    ]


def test_plain_prompt_echoes_only() -> None:
    msgs: list[ModelMessage] = [_user("hello there")]
    assert _names(mock._lead_sequence(msgs)) == ["final_result"]
