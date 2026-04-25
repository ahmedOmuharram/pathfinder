from __future__ import annotations

import asyncio
import re
from collections.abc import AsyncIterator, Callable
from enum import StrEnum

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    UserPromptPart,
)
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, FunctionModel

from pathfinder.ai.agents.supervisor import SupervisorDecision, SupervisorTarget
from pathfinder.ai.graph.state import (
    ClarificationQuestion,
    PhaseDisposition,
    PhaseOutcome,
    ProblemFrame,
    VerificationDigest,
)

_MOCK_PREFIX = "[mock] "
_SLOW_KEYWORD = "slow"
_SLOW_CHUNK_DELAY = 0.1

_PLAN_TRIGGER = re.compile(
    r"create\s+(step|delegation|delegation\s+draft)|artifact\s+graph",
    re.IGNORECASE,
)
_DELEGATION_DRAFT_TRIGGER = re.compile(
    r"create\s+delegation\s+draft", re.IGNORECASE,
)
_SUPERVISOR_PHASE_COUNT_RE = re.compile(
    r"phase_call_counts_this_turn:\s*([^\n]+)",
)
_SUPERVISOR_HAS_ACTIVE_PLAN_RE = re.compile(r"has_active_plan:\s*(True|False)")
_SUPERVISOR_PLAN_STATUS_RE = re.compile(r"plan\.status:\s*(\S+)")
_PLAN_PHASES: tuple[SupervisorTarget, ...] = (
    "scoping",
    "discovery",
    "planning",
    "execution",
    "verification",
)
_SCOPING_TOOL_UNIVERSE: frozenset[str] = frozenset({
    "think",
    "web_search",
    "literature_search",
    "set_problem_frame",
    "note",
    "update_note",
    "delete_note",
    "pin_note",
    "unpin_note",
    "list_notes",
    "search_notes",
    "read_note",
    "promote_to_memory",
})


class _Role(StrEnum):
    SUPERVISOR = "supervisor"
    SCOPING = "scoping"
    DISCOVERY = "discovery"
    PLANNING = "planning"
    EXECUTION = "execution"
    VERIFICATION = "verification"
    UNKNOWN = "unknown"


def _function_tool_names(info: AgentInfo) -> frozenset[str]:
    return frozenset(t.name for t in info.function_tools)


def _output_tool_names(info: AgentInfo) -> frozenset[str]:
    return frozenset(t.name for t in info.output_tools)


def _detect_role(info: AgentInfo) -> _Role:
    fn = _function_tool_names(info)
    out = _output_tool_names(info)
    if "final_result_VerificationDigest" in out:
        return _Role.VERIFICATION
    for marker, role in _ROLE_MARKERS:
        if marker in fn:
            return role
    if "think" in fn and fn.issubset(_SCOPING_TOOL_UNIVERSE):
        return _Role.SCOPING
    if not info.function_tools:
        return _Role.SUPERVISOR
    return _Role.UNKNOWN


_ROLE_MARKERS: tuple[tuple[str, _Role], ...] = (
    ("create_leaf_step", _Role.EXECUTION),
    ("create_plan", _Role.PLANNING),
    ("get_search_overview", _Role.DISCOVERY),
)


def _latest_user_text(messages: list[ModelMessage]) -> str:
    for msg in reversed(messages):
        if not isinstance(msg, ModelRequest):
            continue
        for part in reversed(msg.parts):
            if isinstance(part, UserPromptPart) and isinstance(part.content, str):
                text = part.content.strip()
                if text:
                    return text
    return ""


def _called_tools_this_phase(messages: list[ModelMessage]) -> frozenset[str]:
    boundary = -1
    for i, msg in enumerate(messages):
        if not isinstance(msg, ModelRequest):
            continue
        if any(isinstance(p, UserPromptPart) for p in msg.parts):
            boundary = i
    called: set[str] = set()
    for msg in messages[boundary + 1:]:
        if not isinstance(msg, ModelResponse):
            continue
        for part in msg.parts:
            if isinstance(part, ToolCallPart):
                called.add(part.tool_name)
    return frozenset(called)


def _is_plan_trigger(text: str) -> bool:
    return bool(_PLAN_TRIGGER.search(text))


def _is_delegation_draft(text: str) -> bool:
    return bool(_DELEGATION_DRAFT_TRIGGER.search(text))


def _tool_call(name: str, args: dict[str, object], call_id: str) -> ToolCallPart:
    return ToolCallPart(tool_name=name, args=args, tool_call_id=call_id)


def _scoping_problem_frame() -> ProblemFrame:
    return ProblemFrame(
        user_goal="Create a test strategy",
        interpreted_goal="Build a simple WDK strategy for testing",
        organism_scope="Plasmodium falciparum 3D7",
        record_type="transcript",
        biological_entities=["genes"],
        inclusion_criteria=["taxon membership"],
        success_criteria=["strategy contains a valid WDK leaf step"],
        assumptions=["mock mode uses a deterministic GenesByTaxon plan"],
        blocking_questions=[],
        optional_questions=[
            ClarificationQuestion(
                question="Confirm taxon scope is P. falciparum 3D7?",
                priority="optional",
            ),
        ],
        ready_for_wdk_discovery=True,
        confidence=0.9,
    )


def _scoping_response(messages: list[ModelMessage]) -> ModelResponse:
    called = _called_tools_this_phase(messages)
    if "think" not in called:
        return ModelResponse(parts=[
            _tool_call(
                "think",
                {"thought": "Frame the test prompt as a P. falciparum strategy."},
                "mock_scoping_think",
            ),
        ])
    if not (called & {"web_search", "literature_search"}):
        return ModelResponse(parts=[
            _tool_call(
                "literature_search",
                {"query": "Plasmodium falciparum gene catalog overview"},
                "mock_scoping_lit",
            ),
        ])
    if "set_problem_frame" not in called:
        frame = _scoping_problem_frame()
        return ModelResponse(parts=[
            _tool_call(
                "set_problem_frame",
                {"frame": frame.model_dump(by_alias=True, mode="json")},
                "mock_scoping_frame",
            ),
        ])
    outcome = PhaseOutcome(
        disposition=PhaseDisposition.HANDOFF,
        prose=(
            f"{_MOCK_PREFIX}Scoped the request: P. falciparum 3D7 transcripts. "
            "Continuing to WDK catalog discovery."
        ),
        reason="frame complete; handing off to discovery",
        handoff_to="discovery",
    )
    return ModelResponse(parts=[
        _tool_call(
            "final_result",
            outcome.model_dump(by_alias=True, mode="json"),
            "mock_scoping_final",
        ),
    ])


def _discovery_response(messages: list[ModelMessage]) -> ModelResponse:
    called = _called_tools_this_phase(messages)
    if "get_search_overview" not in called:
        return ModelResponse(parts=[
            _tool_call(
                "get_search_overview",
                {"search_name": "GenesByTaxon"},
                "mock_discovery_overview",
            ),
        ])
    if "update_search_decision" not in called:
        return ModelResponse(parts=[
            _tool_call(
                "update_search_decision",
                {
                    "search_name": "GenesByTaxon",
                    "selection_status": "selected",
                    "rationale": "GenesByTaxon returns all transcripts for a taxon.",
                    "selection_reason": "primary anchor for the test strategy",
                    "confidence": 0.95,
                    "param_hints": {"organism": "Plasmodium falciparum 3D7"},
                },
                "mock_discovery_decision",
            ),
        ])
    outcome = PhaseOutcome(
        disposition=PhaseDisposition.HANDOFF,
        prose=(
            f"{_MOCK_PREFIX}Selected GenesByTaxon for the P. falciparum scope. "
            "Continuing to plan."
        ),
        reason="search universe locked; handing off to planning",
        handoff_to="planning",
    )
    return ModelResponse(parts=[
        _tool_call(
            "final_result",
            outcome.model_dump(by_alias=True, mode="json"),
            "mock_discovery_final",
        ),
    ])


def _planning_response(messages: list[ModelMessage]) -> ModelResponse:
    called = _called_tools_this_phase(messages)
    if "create_plan" not in called:
        return ModelResponse(parts=[
            _tool_call(
                "create_plan",
                {
                    "title": "Mock P. falciparum strategy",
                    "description": "Single-step P. falciparum transcript strategy.",
                    "rationale": "Smallest realistic test strategy.",
                    "steps": [
                        {
                            "id": "step_pftaxon",
                            "search_name": "GenesByTaxon",
                            "display_name": "P. falciparum genes",
                            "record_type": "transcript",
                            "rationale": "All P. falciparum transcripts.",
                            "step_type": "leaf",
                            "parameters": {
                                "organism": ["Plasmodium falciparum 3D7"],
                            },
                        },
                    ],
                    "connections": [],
                },
                "mock_planning_create",
            ),
        ])
    if "submit_plan" not in called:
        return ModelResponse(parts=[
            _tool_call(
                "submit_plan", {}, "mock_planning_submit",
            ),
        ])
    outcome = PhaseOutcome(
        disposition=PhaseDisposition.HANDOFF,
        prose=(
            f"{_MOCK_PREFIX}Plan approved. Handing off to execution."
        ),
        reason="plan approved; running execution",
        handoff_to="execution",
    )
    return ModelResponse(parts=[
        _tool_call(
            "final_result_PhaseOutcome",
            outcome.model_dump(by_alias=True, mode="json"),
            "mock_planning_final",
        ),
    ])


def _execution_response(messages: list[ModelMessage]) -> ModelResponse:
    called = _called_tools_this_phase(messages)
    if "create_leaf_step" not in called:
        return ModelResponse(parts=[
            _tool_call(
                "create_leaf_step",
                {
                    "search_name": "GenesByTaxon",
                    "parameters": {"organism": ["Plasmodium falciparum 3D7"]},
                    "display_name": "P. falciparum genes",
                    "record_type": "transcript",
                },
                "mock_execution_leaf",
            ),
        ])
    outcome = PhaseOutcome(
        disposition=PhaseDisposition.HANDOFF,
        prose=(
            f"{_MOCK_PREFIX}Built the GenesByTaxon step. Handing off to "
            "verification."
        ),
        reason="strategy built; verification next",
        handoff_to="verification",
    )
    return ModelResponse(parts=[
        _tool_call(
            "final_result_PhaseOutcome",
            outcome.model_dump(by_alias=True, mode="json"),
            "mock_execution_final",
        ),
    ])


def _verification_response() -> ModelResponse:
    digest = VerificationDigest(
        disposition=PhaseDisposition.DONE,
        prose=(
            f"{_MOCK_PREFIX}Strategy built and verified end-to-end."
        ),
        reason="mock verification complete",
        success=True,
        key_findings=["Strategy contains the planned GenesByTaxon step."],
        caveats=[],
        remember=[],
    )
    return ModelResponse(parts=[
        _tool_call(
            "final_result_VerificationDigest",
            digest.model_dump(by_alias=True, mode="json"),
            "mock_verification_final",
        ),
    ])


def _supervisor_state_summary(info: AgentInfo) -> dict[str, str]:
    instructions = info.instructions or ""
    summary: dict[str, str] = {}
    match = _SUPERVISOR_PHASE_COUNT_RE.search(instructions)
    if match:
        summary["phases_run"] = match.group(1).strip()
    plan_match = _SUPERVISOR_HAS_ACTIVE_PLAN_RE.search(instructions)
    if plan_match:
        summary["has_active_plan"] = plan_match.group(1)
    status_match = _SUPERVISOR_PLAN_STATUS_RE.search(instructions)
    if status_match:
        summary["plan_status"] = status_match.group(1)
    return summary


def _phases_already_run(state: dict[str, str]) -> set[str]:
    raw = state.get("phases_run", "")
    if not raw:
        return set()
    return {item.split("=", 1)[0].strip() for item in raw.split(",")}


def _next_plan_phase(already_run: set[str]) -> SupervisorTarget:
    for phase in _PLAN_PHASES:
        if phase not in already_run:
            return phase
    return "end"


def _decide_supervisor(
    user_text: str, state: dict[str, str],
) -> SupervisorDecision:
    already_run = _phases_already_run(state)

    if _is_delegation_draft(user_text) and not already_run:
        return SupervisorDecision(
            to="question",
            reason="mock delegation-draft trigger answers without running phases",
            answer=f"{_MOCK_PREFIX}delegation draft acknowledged",
        )

    if _is_plan_trigger(user_text) or already_run:
        target: SupervisorTarget
        if (
            state.get("plan_status") == "approved"
            and "execution" not in already_run
        ):
            target = "execution"
        else:
            target = _next_plan_phase(already_run)
        if target == "end":
            return SupervisorDecision(to="end", reason="mock plan flow complete")
        return SupervisorDecision(to=target, reason=f"mock route to {target}")

    if user_text.lower() == _SLOW_KEYWORD:
        return SupervisorDecision(
            to="end", reason="mock slow trigger does not run phases",
        )
    echo = user_text or "your request"
    return SupervisorDecision(
        to="question",
        reason="mock echoes non-strategy prompts",
        answer=f"{_MOCK_PREFIX}{echo}",
    )


def _supervisor_response(
    messages: list[ModelMessage], info: AgentInfo,
) -> ModelResponse:
    user_text = _latest_user_text(messages)
    state = _supervisor_state_summary(info)
    return _supervisor_decision_response(_decide_supervisor(user_text, state))


def _supervisor_decision_response(decision: SupervisorDecision) -> ModelResponse:
    return ModelResponse(parts=[
        _tool_call(
            "final_result",
            decision.model_dump(by_alias=True, mode="json", exclude_none=True),
            "mock_supervisor_final",
        ),
    ])


_PHASE_HANDLERS: dict[
    _Role, Callable[[list[ModelMessage]], ModelResponse],
] = {
    _Role.SCOPING: _scoping_response,
    _Role.DISCOVERY: _discovery_response,
    _Role.PLANNING: _planning_response,
    _Role.EXECUTION: _execution_response,
    _Role.VERIFICATION: lambda _messages: _verification_response(),
}


def _resolve_response(
    messages: list[ModelMessage], info: AgentInfo,
) -> ModelResponse:
    role = _detect_role(info)
    if role is _Role.SUPERVISOR:
        return _supervisor_response(messages, info)
    handler = _PHASE_HANDLERS.get(role)
    if handler is not None:
        return handler(messages)
    user_text = _latest_user_text(messages)
    echo = user_text or "your request"
    return ModelResponse(parts=[TextPart(content=f"{_MOCK_PREFIX}{echo}")])


def _mock_function(
    messages: list[ModelMessage], info: AgentInfo,
) -> ModelResponse:
    return _resolve_response(messages, info)


async def _mock_stream_function(
    messages: list[ModelMessage], info: AgentInfo,
) -> AsyncIterator[str | dict[int, DeltaToolCall]]:
    user_text = _latest_user_text(messages)
    if user_text.lower() == _SLOW_KEYWORD and _detect_role(info) is not _Role.SUPERVISOR:
        text = f"{_MOCK_PREFIX}Processing slowly..."
        for char in text:
            yield char
            await asyncio.sleep(_SLOW_CHUNK_DELAY)
        return
    response = _resolve_response(messages, info)
    for index, part in enumerate(response.parts):
        if isinstance(part, ToolCallPart):
            yield {
                index: DeltaToolCall(
                    name=part.tool_name,
                    json_args=part.args_as_json_str(),
                    tool_call_id=part.tool_call_id,
                ),
            }
        elif isinstance(part, TextPart):
            yield part.content


def get_mock_model() -> FunctionModel:
    return FunctionModel(
        _mock_function,
        stream_function=_mock_stream_function,
        model_name="mock:deterministic",
    )
