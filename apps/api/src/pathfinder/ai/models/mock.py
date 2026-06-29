"""Deterministic scripted LLM mock for e2e + integration tests.

A single ``FunctionModel`` serves the Lead agent and every sub-agent. It
detects which agent it is serving from the available tool names and drives a
scripted FRAME → BUILD → VERIFY flow. The Lead routes on the latest user
message (plus consult-resume state); sub-agents emit their typed delta via
``final_result``.

Two context vars are set by the sub-agent runner before each sub-agent runs:
``current_site_id`` (so canned criteria target a valid organism on the site)
and ``current_user_text`` (so routing can branch on what the user asked for).
The canned FRAME specs live in ``mock_specs``.
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
    COMBINED_SPEC,
    SINGLE_SPEC,
    SpecPlan,
    frame_call,
    verification_delta,
)

LeadTurnState = Literal["await_user", "complete"]

_CLARIFY_PROSE = (
    "Before I build this, let me **clarify** a few things so the strategy "
    "matches what you mean:\n\n"
    "- **Which** evidence defines 'expressed' — a mass-spec stage or a "
    "microarray percentile?\n"
    "- **How strict** on 'doesn't vary much' — what dN/dS cutoff?\n"
    "- What counts as 'no human equivalent' — which phylogenetic profile "
    "pattern?\n\n"
    "Answer those and I'll frame the strategy."
)
_SUCCESS_PROSE = (
    "**Verified end-to-end.** The strategy framed, built, and verified "
    "cleanly — root size looks right and the leaves are non-empty."
)
_IMPACT_PROSE = (
    "Switching the combine to INTERSECT makes the **operator** **stricter**: "
    "the result **drops** to genes supported by *both* signals. That tightens "
    "specificity at the cost of recall — expect a smaller candidate list."
)
_VARIANT_PROSE = (
    "I ran both search variants and compared their result sets above. Tell me "
    "which direction you'd like to carry into the strategy."
)
_CONTROLS_PROSE = (
    "I've saved your uploaded gene IDs as a control set. We can now score "
    "search variants against them whenever you're ready."
)


class _Role(StrEnum):
    LEAD = "lead"
    FRAME = "frame"
    VERIFICATION = "verification"
    EXECUTION = "execution"
    UNKNOWN = "unknown"


# Ordered (marker tools, role) — first whose markers intersect the agent's
# tool names wins. Lead is first: its dispatch tools are unique to the Lead and
# never appear on a sub-agent. (Do NOT key the Lead on consult_user — approval-
# required deferred tools are excluded from AgentInfo.function_tools.)
_ROLE_MARKERS: tuple[tuple[frozenset[str], _Role], ...] = (
    (
        frozenset(
            {
                "frame_problem",
                "build_strategy",
                "verify_strategy",
                "read_ledger_section",
            }
        ),
        _Role.LEAD,
    ),
    (frozenset({"set_criterion", "set_structure"}), _Role.FRAME),
    (frozenset({"run_control_tests_on_step"}), _Role.VERIFICATION),
    (frozenset({"update_leaf_params", "replace_subtree"}), _Role.EXECUTION),
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


def _joined_user_text(messages: list[ModelMessage]) -> str:
    """All user-prompt text across the run, joined. An attached file rides as
    its own text part, so the attachment block can land in a different part
    from the typed message — scan them all."""
    chunks = [
        part.content
        for msg in messages
        if isinstance(msg, ModelRequest)
        for part in msg.parts
        if isinstance(part, UserPromptPart) and isinstance(part.content, str)
    ]
    return "\n".join(chunks)


def _called_tool_parts(messages: list[ModelMessage]) -> list[ToolCallPart]:
    return [
        part
        for msg in messages
        if isinstance(msg, ModelResponse)
        for part in msg.parts
        if isinstance(part, ToolCallPart)
    ]


def _called_tools(messages: list[ModelMessage]) -> list[str]:
    return [p.tool_name for p in _called_tool_parts(messages)]


def _has_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


# Markers are deliberately specific to the journeys' turn prompts so generic
# biology prompts fall through to the plain echo.
_FIX_MARKERS = ("loosen", "%mamm", "fix the phylogenetic", "fix the pattern")
_IMPACT_MARKERS = ("switching the interpro", "switch the interpro", "interpro/go")
_BUILD_MARKERS = (
    "3d7",
    "trophozoite",
    "derisi",
    "interpro",
    "pf00069",
    "ec 2.7",
    "create step",
    "create delegation",
    "go term strategy",
    "protein kinase go genes",
)
_COMBINED_MARKERS = ("comprehensive kinase strategy", "all parameter types")
_CLARIFY_MARKERS = ("human equivalent", "vary much")
_VARIANT_MARKERS = ("compare two search variants", "compare search variants")
_CONSULT_MARKERS = ("consult me before planning", "ask me design questions")


def _variant_text_params(expression: str) -> dict[str, Any]:
    return {
        "text_expression": {"type": "string", "value": expression},
        "text_fields": {"type": "multi-pick-vocabulary", "values": ["product"]},
        "document_type": {"type": "string", "value": "gene"},
        "text_search_organism": {
            "type": "multi-pick-vocabulary",
            "values": ["Plasmodium falciparum 3D7"],
        },
    }


def _variant_args() -> dict[str, Any]:
    return {
        "variants": [
            {
                "label": "kinase",
                "search_name": "GenesByText",
                "record_type": "transcript",
                "parameters": _variant_text_params("kinase"),
            },
            {
                "label": "phosphatase",
                "search_name": "GenesByText",
                "record_type": "transcript",
                "parameters": _variant_text_params("phosphatase"),
            },
        ],
    }


def _consult_args() -> dict[str, Any]:
    return {
        "questions": [
            {
                "id": "q1",
                "prompt": "Fold-change threshold?",
                "kind": "single_choice",
                "options": [
                    {"label": "2-fold", "recommended": True},
                    {"label": "5-fold"},
                ],
            },
            {
                "id": "q2",
                "prompt": "Include the microarray arm?",
                "kind": "single_choice",
                "options": [{"label": "Yes"}, {"label": "No"}],
            },
        ],
    }


def _attachment_gene_ids(text: str) -> list[str]:
    """Pull the cleaned gene IDs the composer's attachment adapter inlined as
    ``Attached gene-ID list from <name>: ID, ID, ...`` (plain framing so the
    input injection scanner doesn't flag it)."""
    marker = text.find("Attached gene-ID list from")
    if marker == -1:
        return []
    colon = text.find(":", marker)
    if colon == -1:
        return []
    line = text[colon + 1 :].splitlines()[0]
    return [token.strip() for token in line.split(",") if token.strip()]


def _consult_resolved(messages: list[ModelMessage]) -> bool:
    """True only for the FRESH consult resume — the deferred ``consult_user``
    came back with answers and no later user message has superseded it."""
    resolved = False
    for msg in messages:
        if not isinstance(msg, ModelRequest):
            continue
        parts = msg.parts
        has_tool_return = any(isinstance(p, ToolReturnPart) for p in parts)
        if any(
            isinstance(p, ToolReturnPart) and p.tool_name == "consult_user"
            for p in parts
        ):
            resolved = True
        elif not has_tool_return and any(isinstance(p, UserPromptPart) for p in parts):
            resolved = False
    return resolved


# The current site + the user's latest message, set by the sub-agent runner
# before each sub-agent runs so canned criteria target a valid organism.
current_site_id: ContextVar[str] = ContextVar(
    "mock_current_site_id", default="veupathdb"
)
current_user_text: ContextVar[str] = ContextVar("mock_current_user_text", default="")


def _active_spec() -> SpecPlan:
    text = current_user_text.get().lower()
    if _has_any(text, _COMBINED_MARKERS):
        return COMBINED_SPEC
    return SINGLE_SPEC


def _call(name: str, args: dict[str, Any]) -> ToolCallPart:
    return ToolCallPart(
        tool_name=name,
        args=args,
        tool_call_id=f"mock_{name}_{uuid4().hex[:10]}",
    )


def _lead_final(prose: str, next_state: LeadTurnState) -> ToolCallPart:
    return _call("final_result", {"prose": prose, "nextState": next_state})


def _build_sequence(prose: str, next_state: LeadTurnState) -> list[ToolCallPart]:
    return [
        _call("frame_problem", {"reason": "mock frame"}),
        _call("build_strategy", {}),
        _call("verify_strategy", {"reason": "mock verification"}),
        _lead_final(prose, next_state),
    ]


def _lead_sequence(messages: list[ModelMessage]) -> list[ToolCallPart]:
    if _consult_resolved(messages):
        return _build_sequence(_SUCCESS_PROSE, "complete")
    raw = _last_user_text(messages)
    ids = _attachment_gene_ids(_joined_user_text(messages))
    if ids:
        return [
            _call(
                "build_control_set",
                {"name": "Uploaded controls", "positive_ids": ids},
            ),
            _lead_final(_CONTROLS_PROSE, "await_user"),
        ]
    return _routed_sequence(raw)


def _routed_sequence(raw: str) -> list[ToolCallPart]:
    lowered = raw.lower()
    if _has_any(lowered, _VARIANT_MARKERS):
        return [
            _call("compare_search_variants", _variant_args()),
            _lead_final(_VARIANT_PROSE, "await_user"),
        ]
    if _has_any(lowered, _CONSULT_MARKERS):
        return [_call("consult_user", _consult_args())]
    if _has_any(lowered, _IMPACT_MARKERS):
        return [_lead_final(_IMPACT_PROSE, "await_user")]
    if _has_any(lowered, _CLARIFY_MARKERS):
        return [_lead_final(_CLARIFY_PROSE, "await_user")]
    build = _FIX_MARKERS + _BUILD_MARKERS + _COMBINED_MARKERS
    if _has_any(lowered, build):
        return _build_sequence(_SUCCESS_PROSE, "complete")
    return [_lead_final(f"[mock] {raw}", "await_user")]


def _next_lead_call(messages: list[ModelMessage]) -> ToolCallPart:
    seq = _lead_sequence(messages)
    called = _called_tools(messages)
    for step in seq:
        if step.tool_name == "final_result":
            return step
        if step.tool_name not in called:
            return step
    return seq[-1]


def _next_frame_call(messages: list[ModelMessage]) -> ToolCallPart:
    return frame_call(_active_spec(), _called_tool_parts(messages))


def _response_part(messages: list[ModelMessage], info: AgentInfo) -> ToolCallPart:
    role = _detect_role(info)
    if role is _Role.LEAD:
        return _next_lead_call(messages)
    if role is _Role.FRAME:
        return _next_frame_call(messages)
    if role is _Role.VERIFICATION:
        text = current_user_text.get().lower()
        success = not _has_any(text, _CLARIFY_MARKERS)
        return _call("final_result", verification_delta(success=success))
    if role is _Role.EXECUTION:
        return _call(
            "final_result",
            {"actionsTaken": ["[mock] recovery"], "followUpNeeded": False},
        )
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
