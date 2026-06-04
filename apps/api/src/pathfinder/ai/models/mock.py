"""Deterministic scripted LLM mock for e2e + integration tests.

A single ``FunctionModel`` serves the Lead agent and every sub-agent. It
detects which agent it is serving from the available tool names, reads the
turn's first user prompt to pick a scripted flow, and returns the next tool
call in that flow based on what's already been called. Sub-agents emit their
typed delta via ``final_result``; the Lead drives sub-agent tools +
``submit_plan_for_approval`` and finishes with a ``LeadResponse``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from enum import StrEnum
from typing import Any, Literal
from uuid import uuid4

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ToolCallPart,
    UserPromptPart,
)
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, FunctionModel

LeadTurnState = Literal["await_user", "complete"]

_MOCK_PROSE = "[mock] Done."


class _Role(StrEnum):
    LEAD = "lead"
    PLANNING = "planning"
    DISCOVERY = "discovery"
    SCOPING = "scoping"
    VERIFICATION = "verification"
    EXECUTION = "execution"
    UNKNOWN = "unknown"


# Ordered (marker tools, role) — first whose markers intersect the agent's
# tool names wins. Lead is first: its marker is unique to the Lead. Planning's
# toolset swaps create_plan↔update_plan once a plan exists, so it lists all of
# its plan tools (a single marker would miss the post-create_plan call).
_ROLE_MARKERS: tuple[tuple[frozenset[str], _Role], ...] = (
    (frozenset({"submit_plan_for_approval"}), _Role.LEAD),
    (frozenset({"create_plan", "update_plan", "submit_plan"}), _Role.PLANNING),
    (frozenset({"run_control_tests_on_step"}), _Role.VERIFICATION),
    (frozenset({"search_for_searches"}), _Role.DISCOVERY),
    (frozenset({"update_leaf_params", "replace_subtree"}), _Role.EXECUTION),
    (frozenset({"set_problem_frame", "save_problem_frame"}), _Role.SCOPING),
)


def _tool_names(info: AgentInfo) -> frozenset[str]:
    return frozenset(t.name for t in info.function_tools)


def _detect_role(info: AgentInfo) -> _Role:
    names = _tool_names(info)
    for markers, role in _ROLE_MARKERS:
        if markers & names:
            return role
    return _Role.UNKNOWN


def _first_user_text(messages: list[ModelMessage]) -> str:
    for msg in messages:
        if isinstance(msg, ModelRequest):
            for part in msg.parts:
                if isinstance(part, UserPromptPart) and isinstance(part.content, str):
                    return part.content
    return ""


def _called_tools(messages: list[ModelMessage]) -> list[str]:
    return [
        part.tool_name
        for msg in messages
        if isinstance(msg, ModelResponse)
        for part in msg.parts
        if isinstance(part, ToolCallPart)
    ]


def _is_build_trigger(text: str) -> bool:
    """All build prompts ("create step", "create delegation",
    "create delegation draft") drive the same plan→approve→execute flow.
    The draft test stops at the approval card (never approves), so the
    execute tail simply isn't reached."""
    lowered = text.lower()
    return "create step" in lowered or "create delegation" in lowered


_STEP_ID = "pf_genes"
_SEARCH = "GenesByTaxon"
_DISPLAY = "Plasmodium falciparum genes"
_ORGANISM = "Plasmodium falciparum 3D7"
_TITLE = "Plasmodium falciparum genes (mock)"
_DESCRIPTION = "Single-step strategy returning all Plasmodium falciparum 3D7 genes."
_RATIONALE = "GenesByTaxon scoped to P. falciparum 3D7 returns the full gene set."
_STEP_RATIONALE = "All genes for the P. falciparum 3D7 organism."

# (name, param_type, typed ParamValue) — matches the real veupathdb
# GenesByTaxon WDK spec: organism is a multi-pick-vocabulary.
_PARAMS: tuple[tuple[str, str, dict[str, Any]], ...] = (
    (
        "organism",
        "multi-pick-vocabulary",
        {"type": "multi-pick-vocabulary", "values": [_ORGANISM]},
    ),
)

_CREATE_PLAN_ARGS: dict[str, Any] = {
    "title": _TITLE,
    "description": _DESCRIPTION,
    "rationale": _RATIONALE,
    "steps": [
        {
            "id": _STEP_ID,
            "search_name": _SEARCH,
            "display_name": _DISPLAY,
            "record_type": "transcript",
            "rationale": _STEP_RATIONALE,
            "parameters": {name: value for name, _kind, value in _PARAMS},
        },
    ],
    "connections": [],
}


def _planned_param(name: str, kind: str, value: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "displayName": name.replace("_", " ").title(),
        "paramType": kind,
        "value": value,
        "status": "set",
        "required": True,
    }


_PLAN_DELTA: dict[str, Any] = {
    "plan": {
        "title": _TITLE,
        "description": _DESCRIPTION,
        "rationale": _RATIONALE,
        "steps": [
            {
                "id": _STEP_ID,
                "searchName": _SEARCH,
                "displayName": _DISPLAY,
                "recordType": "transcript",
                "rationale": _STEP_RATIONALE,
                "stepType": "leaf",
                "status": "ready",
                "parameters": [
                    _planned_param(name, kind, value) for name, kind, value in _PARAMS
                ],
            },
        ],
        "connections": [],
    },
}


def _call(name: str, args: dict[str, Any]) -> ToolCallPart:
    return ToolCallPart(
        tool_name=name,
        args=args,
        tool_call_id=f"mock_{name}_{uuid4().hex[:10]}",
    )


def _lead_final(prose: str, next_state: LeadTurnState) -> ToolCallPart:
    return _call("final_result", {"prose": prose, "nextState": next_state})


def _lead_sequence(text: str) -> list[ToolCallPart]:
    if _is_build_trigger(text):
        return [
            _call("build_plan", {"reason": "mock plan"}),
            _call("submit_plan_for_approval", {}),
            _call("execute_plan", {}),
            _lead_final(_MOCK_PROSE, "complete"),
        ]
    return [_lead_final(f"[mock] {text}", "await_user")]


def _next_lead_call(messages: list[ModelMessage]) -> ToolCallPart:
    seq = _lead_sequence(_first_user_text(messages))
    called = _called_tools(messages)
    for step in seq:
        if step.tool_name == "final_result":
            return step
        if step.tool_name not in called:
            return step
    return seq[-1]


def _next_planning_call(messages: list[ModelMessage]) -> ToolCallPart:
    if "create_plan" not in _called_tools(messages):
        return _call("create_plan", _CREATE_PLAN_ARGS)
    return _call("final_result", _PLAN_DELTA)


def _response_part(messages: list[ModelMessage], info: AgentInfo) -> ToolCallPart:
    role = _detect_role(info)
    if role is _Role.LEAD:
        return _next_lead_call(messages)
    if role is _Role.PLANNING:
        return _next_planning_call(messages)
    return _call("final_result", {})


def _mock_function(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    return ModelResponse(parts=[_response_part(messages, info)])


async def _mock_stream_function(
    messages: list[ModelMessage],
    info: AgentInfo,
) -> AsyncIterator[str | dict[int, DeltaToolCall]]:
    part = _response_part(messages, info)
    yield {
        0: DeltaToolCall(
            name=part.tool_name,
            json_args=part.args_as_json_str(),
            tool_call_id=part.tool_call_id,
        ),
    }


def get_mock_model() -> FunctionModel:
    return FunctionModel(
        _mock_function,
        stream_function=_mock_stream_function,
        model_name="mock:deterministic",
    )


__all__ = ["get_mock_model"]
