"""Deterministic scripted LLM mock for e2e + integration tests.

A single ``FunctionModel`` serves the Lead agent and every sub-agent. It
detects which agent it is serving from the available tool names and drives
a scripted flow. For the Lead it routes on the latest user message plus the
plan-approval state (a denied ``submit_plan_for_approval`` carries
``outcome='denied'``); sub-agents emit their typed delta via ``final_result``.

Two context vars are set by the sub-agent runner before each sub-agent runs:
``current_site_id`` (so canned plans target a search/organism valid on the
site) and ``current_user_text`` (so the planner can branch the canned plan on
what the user asked for). The canned plan specs live in ``mock_specs``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextvars import ContextVar
from enum import StrEnum
from typing import Any, Literal
from uuid import uuid4

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, FunctionModel

from pathfinder.ai.models.mock_specs import (
    INTERPRO_SPEC,
    PLASMO_SPEC,
    TEXT_SPEC,
    PlanSpec,
    create_plan_args,
    plan_delta,
    verification_delta,
)

LeadTurnState = Literal["await_user", "complete"]

_MOCK_PROSE = "[mock] Done."

_CLARIFY_PROSE = (
    "Before I build this, let me **clarify** a few things so the strategy "
    "matches what you mean:\n\n"
    "- **Which** evidence defines 'expressed' — a mass-spec stage or a "
    "microarray percentile?\n"
    "- **How strict** on 'doesn't vary much' — what dN/dS cutoff?\n"
    "- What counts as 'no human equivalent' — which phylogenetic profile "
    "pattern?\n\n"
    "Answer those and I'll draft the plan."
)
_DENY_PROSE = (
    "Understood — I've set that draft aside. Tell me what you'd like to "
    "change and I'll revise the plan."
)
_FAIL_PROSE = (
    "Verification flagged a problem: the phylogenetic-profile leaf "
    "**returned 0** genes — the pattern `%hsap:N%pfal:Y%` is **too narrow**. "
    "**Loosen** it (e.g. broaden the human side) and I'll re-run."
)
_SUCCESS_PROSE = (
    "**Verified end-to-end.** The loosened pattern resolves cleanly and the "
    "strategy now yields a usable list of **candidate drug targets** — root "
    "size looks right and the leaves are non-empty."
)
_IMPACT_PROSE = (
    "Switching the InterPro/GO combine to INTERSECT makes the **operator** "
    "**stricter**: the result **drops** to genes supported by *both* signals. "
    "That tightens specificity at the cost of recall — expect a smaller "
    "candidate list."
)


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


def _last_user_text(messages: list[ModelMessage]) -> str:
    text = ""
    for msg in messages:
        if isinstance(msg, ModelRequest):
            for part in msg.parts:
                if isinstance(part, UserPromptPart) and isinstance(part.content, str):
                    text = part.content
    return text


def _called_tools(messages: list[ModelMessage]) -> list[str]:
    return [
        part.tool_name
        for msg in messages
        if isinstance(msg, ModelResponse)
        for part in msg.parts
        if isinstance(part, ToolCallPart)
    ]


def _submit_approval_outcome(
    messages: list[ModelMessage],
) -> Literal["approved", "denied"] | None:
    """Inspect resumed messages for the resolved ``submit_plan_for_approval``.

    A denied deferred tool is recorded as a ``ToolReturnPart`` with
    ``outcome='denied'``; an approved one runs the tool body and returns the
    plan with a normal outcome. ``None`` means the plan hasn't been
    submitted-and-resolved in this run (a fresh, non-resume turn)."""
    outcome: Literal["approved", "denied"] | None = None
    for msg in messages:
        if not isinstance(msg, ModelRequest):
            continue
        for part in msg.parts:
            if (
                isinstance(part, ToolReturnPart)
                and part.tool_name == "submit_plan_for_approval"
            ):
                outcome = "denied" if part.outcome == "denied" else "approved"
    return outcome


def _is_build_trigger(text: str) -> bool:
    """The legacy build prompts ("create step", "create delegation",
    "create delegation draft") drive a plan→approve→execute flow. The draft
    test stops at the approval card, so the execute tail isn't reached."""
    lowered = text.lower()
    return "create step" in lowered or "create delegation" in lowered


def _has_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


# Markers are deliberately specific to the plasmodium-drug-targets journey's
# turn prompts so generic biology prompts in other journeys fall through to the
# plain echo. Order in _text_sequence is FIX → IMPACT → PLAN → CLARIFY.
_FIX_MARKERS = ("loosen", "%mamm", "fix the phylogenetic", "fix the pattern")
_IMPACT_MARKERS = ("switching the interpro", "switch the interpro", "interpro/go")
_PLAN_MARKERS = (
    "3d7",
    "trophozoite",
    "derisi",
    "interpro",
    "pf00069",
    "ec 2.7",
)
_CLARIFY_MARKERS = ("human equivalent", "vary much")


# The current site + the user's latest message, set by the sub-agent runner
# before each sub-agent runs so canned plans target a valid search/organism
# and branch on what the user asked for.
current_site_id: ContextVar[str] = ContextVar(
    "mock_current_site_id", default="veupathdb"
)
current_user_text: ContextVar[str] = ContextVar("mock_current_user_text", default="")
_PLASMO_SITES = frozenset({"plasmodb", "veupathdb"})


def _active_spec() -> PlanSpec:
    if _has_any(current_user_text.get().lower(), _PLAN_MARKERS):
        return INTERPRO_SPEC
    return PLASMO_SPEC if current_site_id.get() in _PLASMO_SITES else TEXT_SPEC


def _call(name: str, args: dict[str, Any]) -> ToolCallPart:
    return ToolCallPart(
        tool_name=name,
        args=args,
        tool_call_id=f"mock_{name}_{uuid4().hex[:10]}",
    )


def _lead_final(prose: str, next_state: LeadTurnState) -> ToolCallPart:
    return _call("final_result", {"prose": prose, "nextState": next_state})


def _execute_then_verify(prose: str, next_state: LeadTurnState) -> list[ToolCallPart]:
    return [
        _call("execute_plan", {}),
        _call("verify_strategy", {"reason": "mock verification"}),
        _lead_final(prose, next_state),
    ]


def _resume_sequence(
    outcome: Literal["approved", "denied"] | None,
) -> list[ToolCallPart] | None:
    if outcome == "denied":
        return [_lead_final(_DENY_PROSE, "await_user")]
    if outcome == "approved":
        return _execute_then_verify(_FAIL_PROSE, "await_user")
    return None


def _text_sequence(raw: str) -> list[ToolCallPart]:
    text = raw.lower()
    if _is_build_trigger(text):
        return [
            _call("build_plan", {"reason": "mock plan"}),
            _call("submit_plan_for_approval", {}),
            _call("execute_plan", {}),
            _lead_final(_MOCK_PROSE, "complete"),
        ]
    if _has_any(text, _FIX_MARKERS):
        return _execute_then_verify(_SUCCESS_PROSE, "complete")
    if _has_any(text, _IMPACT_MARKERS):
        return [_lead_final(_IMPACT_PROSE, "await_user")]
    if _has_any(text, _PLAN_MARKERS):
        return [
            _call("build_plan", {"reason": "mock plan"}),
            _call("submit_plan_for_approval", {}),
        ]
    if _has_any(text, _CLARIFY_MARKERS):
        return [_lead_final(_CLARIFY_PROSE, "await_user")]
    return [_lead_final(f"[mock] {raw}", "await_user")]


def _lead_sequence(messages: list[ModelMessage]) -> list[ToolCallPart]:
    resume = _resume_sequence(_submit_approval_outcome(messages))
    if resume is not None:
        return resume
    return _text_sequence(_last_user_text(messages))


def _next_lead_call(messages: list[ModelMessage]) -> ToolCallPart:
    seq = _lead_sequence(messages)
    called = _called_tools(messages)
    for step in seq:
        if step.tool_name == "final_result":
            return step
        if step.tool_name not in called:
            return step
    return seq[-1]


def _next_planning_call(messages: list[ModelMessage], info: AgentInfo) -> ToolCallPart:
    tools = _tool_names(info)
    # On a re-plan the toolset swaps create_plan→update_plan; the plan already
    # exists, so just emit the typed delta and leave the active plan as-is.
    if "create_plan" in tools and "create_plan" not in _called_tools(messages):
        return _call("create_plan", create_plan_args(_active_spec()))
    return _call("final_result", plan_delta(_active_spec()))


def _response_part(messages: list[ModelMessage], info: AgentInfo) -> ToolCallPart:
    role = _detect_role(info)
    if role is _Role.LEAD:
        return _next_lead_call(messages)
    if role is _Role.PLANNING:
        return _next_planning_call(messages, info)
    if role is _Role.VERIFICATION:
        success = _has_any(current_user_text.get().lower(), _FIX_MARKERS)
        return _call("final_result", verification_delta(success=success))
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


__all__ = ["current_site_id", "current_user_text", "get_mock_model"]
