"""The deterministic mock's Lead routing: approval resume, deny→rebuild, and
the consult/variant/attachment journeys. These drive the e2e chat flows, so a
regression here silently reds the whole browser suite."""

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


def _submit_call() -> ModelResponse:
    return ModelResponse(
        parts=[
            ToolCallPart(
                tool_name="submit_plan_for_approval", args={}, tool_call_id="s1"
            )
        ]
    )


def _submit_return(outcome: str) -> ModelRequest:
    return ModelRequest(
        parts=[
            ToolReturnPart(
                tool_name="submit_plan_for_approval",
                content="ok",
                tool_call_id="s1",
                outcome=outcome,
            )
        ]
    )


def _names(seq: list[ToolCallPart]) -> list[str]:
    return [c.tool_name for c in seq]


def test_fresh_approval_resumes_to_execute() -> None:
    msgs: list[ModelMessage] = [
        _user("...3d7...interpro..."),
        _submit_call(),
        _submit_return("approved"),
    ]
    assert "execute_plan" in _names(mock._lead_sequence(msgs))


def test_fresh_denial_resumes_to_deny_prose() -> None:
    msgs: list[ModelMessage] = [
        _user("...3d7...interpro..."),
        _submit_call(),
        _submit_return("denied"),
    ]
    assert _names(mock._lead_sequence(msgs)) == ["final_result"]


def test_user_message_after_denial_rebuilds_instead_of_redenying() -> None:
    # The user denied, got the "set that draft aside" prose, then asked for a
    # change. The stale denied submit must NOT trigger another deny — it must
    # build a fresh plan.
    msgs: list[ModelMessage] = [
        _user("...3d7...interpro..."),
        _submit_call(),
        _submit_return("denied"),
        ModelResponse(
            parts=[ToolCallPart(tool_name="final_result", args={}, tool_call_id="f1")]
        ),
        _user("Add InterPro PF00069 and EC 2.7 to broaden kinase identification."),
    ]
    assert _names(mock._lead_sequence(msgs)) == [
        "build_plan",
        "submit_plan_for_approval",
    ]


def test_consult_resume_builds_plan() -> None:
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
        "build_plan",
        "submit_plan_for_approval",
    ]


def test_user_message_after_approval_does_not_re_execute() -> None:
    msgs: list[ModelMessage] = [
        _user("...3d7...interpro..."),
        _submit_call(),
        _submit_return("approved"),
        ModelResponse(
            parts=[ToolCallPart(tool_name="execute_plan", args={}, tool_call_id="e1")]
        ),
        _user("now show me the kinase genes only"),
    ]
    assert "execute_plan" not in _names(mock._lead_sequence(msgs))
