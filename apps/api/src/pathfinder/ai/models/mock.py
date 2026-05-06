from __future__ import annotations

import asyncio
import re
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import uuid4

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
_RESEARCH_QUESTION_TRIGGER = re.compile(
    r"\b(gene|genes|kinase|kinases|plasmodium|gametocyte|transcript|"
    r"protein|orthology|orthologs?|expression|GO[\s:]+term|GO:\d+|"
    r"taxon|organism|signal\s+peptide|transmembrane|metabolic|"
    r"enrichment|upregulated|downregulated|differentially\s+expressed)\b",
    re.IGNORECASE,
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


def _detect_role(
    info: AgentInfo, messages: list[ModelMessage] | None = None,
) -> _Role:
    fn = _function_tool_names(info)
    for marker, role in _ROLE_MARKERS:
        if marker in fn:
            return role
    if "think" in fn and fn.issubset(_SCOPING_TOOL_UNIVERSE):
        return _Role.SCOPING
    if messages is not None:
        history_role = _role_from_history(messages)
        if history_role is not None:
            return history_role
    if not info.function_tools:
        return _Role.SUPERVISOR
    return _Role.UNKNOWN


# Each marker is a tool that ONLY appears in that one agent's surface.
# Confirmed by inspecting agent.override(model=FunctionModel(capture)).run()
# against each agent in graph/runtime — see /tmp/inspect_agents.py output.
_ROLE_MARKERS: tuple[tuple[str, _Role], ...] = (
    ("journal", _Role.SUPERVISOR),
    ("search_for_searches", _Role.DISCOVERY),
    ("create_plan", _Role.PLANNING),
    ("build_strategy", _Role.EXECUTION),
    ("run_gene_set_enrichment", _Role.VERIFICATION),
)

_HISTORY_ROLE_MARKERS: tuple[tuple[str, _Role], ...] = (
    ("set_problem_frame", _Role.SCOPING),
    ("search_for_searches", _Role.DISCOVERY),
    ("update_search_decision", _Role.DISCOVERY),
    ("create_plan", _Role.PLANNING),
    ("submit_plan", _Role.PLANNING),
    ("build_strategy", _Role.EXECUTION),
    ("run_gene_set_enrichment", _Role.VERIFICATION),
)


def _role_from_history(messages: list[ModelMessage]) -> _Role | None:
    boundary = -1
    for i, msg in enumerate(messages):
        if not isinstance(msg, ModelRequest):
            continue
        if any(isinstance(p, UserPromptPart) for p in msg.parts):
            boundary = i
    for msg in reversed(messages[boundary + 1:]):
        if not isinstance(msg, ModelResponse):
            continue
        for part in msg.parts:
            if not isinstance(part, ToolCallPart):
                continue
            for marker, role in _HISTORY_ROLE_MARKERS:
                if part.tool_name == marker:
                    return role
    return None


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


def _is_research_question(text: str) -> bool:
    return bool(_RESEARCH_QUESTION_TRIGGER.search(text))


def _tool_call(
    name: str, args: dict[str, object], label: str,
) -> ToolCallPart:
    return ToolCallPart(
        tool_name=name, args=args, tool_call_id=f"{label}_{uuid4().hex[:12]}",
    )


def _scoping_problem_frame(user_text: str) -> ProblemFrame:
    return ProblemFrame(
        user_goal=user_text or "Find Plasmodium kinase genes",
        interpreted_goal=(
            "Identify Plasmodium falciparum genes annotated with kinase "
            "activity (GO:0016301), with curated or computed evidence."
        ),
        organism_scope="Plasmodium falciparum 3D7",
        record_type="transcript",
        biological_entities=["kinase", "GO:0016301"],
        inclusion_criteria=[
            "GO:0016301 kinase activity annotation",
            "Curated or Computed evidence",
        ],
        success_criteria=[
            "Ranked list of Plasmodium kinase genes",
            "Each gene annotated with GO term and evidence",
        ],
        assumptions=[
            "Using P. falciparum 3D7 reference strain (PlasmoDB default)",
            "Using GO:0016301 (kinase activity) as the canonical kinase term",
        ],
        blocking_questions=[],
        optional_questions=[
            ClarificationQuestion(
                question="Should we narrow to a specific kinase family (e.g. tyrosine kinases) or include all kinase activity annotations?",
                context="GO:0016301 is the broad kinase activity term; subterms exist for specific families.",
                field="biological_entities",
                priority="optional",
            ),
        ],
        ready_for_wdk_discovery=True,
        confidence=0.85,
    )


_StepArgs = dict[str, Any] | Callable[[list[ModelMessage]], dict[str, Any]]


@dataclass(frozen=True)
class _Step:
    tool: str
    args: _StepArgs
    aliases: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class _Flow:
    steps: tuple[_Step, ...]
    final: PhaseOutcome | VerificationDigest


def _scoping_frame_args(messages: list[ModelMessage]) -> dict[str, Any]:
    return _scoping_problem_frame(_latest_user_text(messages)).model_dump(
        by_alias=True, mode="json", exclude_none=True,
    )


_KINASE_PLAN: dict[str, Any] = {
    "title": "Plasmodium kinase genes (GO:0016301)",
    "description": (
        "Single-step strategy returning Plasmodium falciparum transcripts "
        "annotated with kinase activity."
    ),
    "rationale": (
        "GenesByGoTerm with GO:0016301 (kinase activity) and Curated/Computed "
        "evidence captures the canonical kinase set on PlasmoDB."
    ),
    "steps": [
        {
            "id": "kinase",
            "search_name": "GenesByGoTerm",
            "display_name": "Plasmodium Kinases (GO:0016301)",
            "record_type": "transcript",
            "rationale": (
                "Find Plasmodium genes annotated with kinase activity "
                "(curated or computed evidence)."
            ),
            "step_type": "leaf",
            "parameters": {
                "organism": ["Plasmodium falciparum 3D7"],
                "go_term": "GO:0016301",
                "go_term_slim": "No",
                "go_typeahead": ["GO:0016301"],
                "go_term_evidence": ["Curated", "Computed"],
            },
        },
    ],
    "connections": [],
}

_KINASE_BUILD: dict[str, Any] = {
    "root": {
        "searchName": "GenesByGoTerm",
        "displayName": "Plasmodium Kinases (GO:0016301)",
        "parameters": {
            "organism": ["Plasmodium falciparum 3D7"],
            "go_term": "GO:0016301",
            "go_term_slim": "No",
            "go_typeahead": ["GO:0016301"],
            "go_term_evidence": ["Curated", "Computed"],
        },
    },
    "name": "Plasmodium kinase genes (mock)",
    "description": (
        "Plasmodium falciparum genes annotated with kinase activity "
        "(GO:0016301)."
    ),
}

_FLOWS: dict[_Role, _Flow] = {
    _Role.SCOPING: _Flow(
        steps=(
            _Step(
                tool="think",
                args={
                    "thought": (
                        "Frame as a Plasmodium kinase gene query. "
                        "GO:0016301 is the canonical kinase activity term."
                    ),
                },
            ),
            _Step(
                tool="literature_search",
                args={"query": "Plasmodium falciparum kinase GO:0016301 review"},
                aliases=frozenset({"web_search"}),
            ),
            _Step(tool="set_problem_frame", args=_scoping_frame_args),
        ),
        final=PhaseOutcome(
            disposition=PhaseDisposition.HANDOFF,
            prose=(
                f"{_MOCK_PREFIX}Scoped: Plasmodium falciparum kinase genes "
                "(GO:0016301). Handing off to WDK catalog discovery."
            ),
            reason="frame complete; handing off to discovery",
            handoff_to="discovery",
        ),
    ),
    _Role.DISCOVERY: _Flow(
        steps=(
            _Step(
                tool="search_for_searches",
                args={
                    "query": "kinase activity GO term Plasmodium",
                    "record_type": "gene",
                    "limit": 10,
                },
            ),
            _Step(
                tool="get_search_overview",
                args={"search_name": "GenesByGoTerm"},
            ),
            _Step(
                tool="update_search_decision",
                args={
                    "search_name": "GenesByGoTerm",
                    "selection_status": "selected",
                    "rationale": (
                        "GenesByGoTerm finds genes by GO annotation. "
                        "Use GO:0016301 (kinase activity) for the kinase scope."
                    ),
                    "selection_reason": "Primary anchor for kinase activity scoping.",
                    "confidence": 0.95,
                    "param_hints": {
                        "organism": "Plasmodium falciparum 3D7",
                        "go_term": "GO:0016301",
                        "go_term_evidence": "Curated, Computed",
                    },
                },
            ),
        ),
        final=PhaseOutcome(
            disposition=PhaseDisposition.HANDOFF,
            prose=(
                f"{_MOCK_PREFIX}Selected GenesByGoTerm with GO:0016301 "
                "(kinase activity) as the primary search. Handing off to planning."
            ),
            reason="search universe locked; handing off to planning",
            handoff_to="planning",
        ),
    ),
    _Role.PLANNING: _Flow(
        steps=(
            _Step(tool="create_plan", args=_KINASE_PLAN),
            _Step(tool="submit_plan", args={}),
        ),
        final=PhaseOutcome(
            disposition=PhaseDisposition.HANDOFF,
            prose=f"{_MOCK_PREFIX}Plan approved. Handing off to execution.",
            reason="plan approved; running execution",
            handoff_to="execution",
        ),
    ),
    _Role.EXECUTION: _Flow(
        steps=(_Step(tool="build_strategy", args=_KINASE_BUILD),),
        final=PhaseOutcome(
            disposition=PhaseDisposition.HANDOFF,
            prose=(
                f"{_MOCK_PREFIX}Built the GenesByGoTerm strategy for kinase "
                "activity. Handing off to verification."
            ),
            reason="strategy built; verification next",
            handoff_to="verification",
        ),
    ),
    _Role.VERIFICATION: _Flow(
        steps=(),
        final=VerificationDigest(
            disposition=PhaseDisposition.DONE,
            prose=(
                f"{_MOCK_PREFIX}Strategy built and verified end-to-end. "
                "GenesByGoTerm with GO:0016301 (kinase activity) returns the "
                "Plasmodium kinase set."
            ),
            reason="mock verification complete",
            success=True,
            key_findings=[
                "Strategy contains a GenesByGoTerm leaf with GO:0016301.",
                "Organism scoped to Plasmodium falciparum 3D7.",
                "Evidence filter: Curated + Computed.",
            ],
            caveats=[
                "Mock response — no real LLM reasoning. The kinase scope is "
                "hardcoded; for other questions reuse this strategy as a template.",
            ],
            remember=[],
        ),
    ),
}


def _drive_phase(role: _Role, messages: list[ModelMessage]) -> ModelResponse:
    flow = _FLOWS[role]
    called = _called_tools_this_phase(messages)
    for step in flow.steps:
        if step.tool in called or (step.aliases & called):
            continue
        args = step.args(messages) if callable(step.args) else step.args
        return ModelResponse(parts=[_tool_call(step.tool, args, step.tool)])
    return ModelResponse(parts=[
        _tool_call(
            "final_result",
            flow.final.model_dump(by_alias=True, mode="json"),
            f"{role.value}_final",
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

    if (
        _is_plan_trigger(user_text)
        or _is_research_question(user_text)
        or already_run
    ):
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


def _resolve_response(
    messages: list[ModelMessage], info: AgentInfo,
) -> ModelResponse:
    role = _detect_role(info, messages)
    if role is _Role.SUPERVISOR:
        return _supervisor_response(messages, info)
    if role in _FLOWS:
        return _drive_phase(role, messages)
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
    if user_text.lower() == _SLOW_KEYWORD and _detect_role(info, messages) is not _Role.SUPERVISOR:
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
