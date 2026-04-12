"""Keyword-triggered, phase-aware mock model for E2E and integration testing.

A pydantic-ai ``FunctionModel`` that detects keywords in the user's
message AND checks which tools are
available (via ``AgentInfo.function_tools``) to return phase-appropriate
responses.

The pipeline runs five phases per turn (scoping → discovery → planning →
execution → verification).  Each phase has a distinct toolset, so the mock uses the
required_tool field in each ``_Trigger`` to respond to exactly the right
phase.

All downstream systems (WDK, PostgreSQL, Redis, gene sets, auto-build)
still run real — only the LLM inference is mocked.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, FunctionModel

_MOCK_PREFIX = "[mock] "
_SLOW_KEYWORD = "slow"
_SLOW_CHUNK_DELAY = 0.1  # seconds between chars in slow mode


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _available_tool_names(info: AgentInfo) -> frozenset[str]:
    """Extract the set of tool names available in the current agent."""
    return frozenset(t.name for t in info.function_tools)


def _extract_user_text(messages: list[ModelMessage]) -> str:
    """Extract the most recent non-empty user prompt from message history."""
    for msg in reversed(messages):
        if not isinstance(msg, ModelRequest):
            continue
        for part in reversed(msg.parts):
            if isinstance(part, UserPromptPart) and isinstance(part.content, str):
                text = part.content.lower().strip()
                if text:
                    return text
    return ""


def _count_tool_returns(messages: list[ModelMessage]) -> int:
    """Count ToolReturnPart instances after the last UserPromptPart.

    Resets at phase boundaries: when ``message_history`` from a prior
    phase is prepended, only tool returns from the CURRENT phase count
    toward the step index.
    """
    # Find the index of the message containing the last UserPromptPart.
    boundary = -1
    for i, msg in enumerate(messages):
        if not isinstance(msg, ModelRequest):
            continue
        if any(isinstance(p, UserPromptPart) for p in msg.parts):
            boundary = i

    # Count tool returns AFTER that boundary message.
    count = 0
    for msg in messages[boundary + 1 :]:
        if not isinstance(msg, ModelRequest):
            continue
        count += sum(1 for p in msg.parts if isinstance(p, ToolReturnPart))
    return count


# ---------------------------------------------------------------------------
# Tool-call factories
# ---------------------------------------------------------------------------


def _discover_taxon() -> ToolCallPart:
    """Call get_search_overview for GenesByTaxon (discovery gate)."""
    return ToolCallPart(
        tool_name="get_search_overview",
        args=json.dumps({"search_name": "GenesByTaxon"}),
        tool_call_id="mock_discover_taxon",
    )


def _set_problem_frame() -> ToolCallPart:
    """Call set_problem_frame for the scoping gate."""
    return ToolCallPart(
        tool_name="set_problem_frame",
        args=json.dumps({
            "userGoal": "Create a test strategy",
            "interpretedGoal": "Build a simple WDK strategy for testing",
            "organismScope": "Plasmodium falciparum 3D7",
            "recordType": "transcript",
            "biologicalEntities": ["genes"],
            "inclusionCriteria": ["taxon membership"],
            "successCriteria": ["strategy contains a valid WDK leaf step"],
            "assumptions": ["mock mode uses a deterministic GenesByTaxon plan"],
            "readyForWdkDiscovery": True,
            "confidence": 0.9,
        }),
        tool_call_id="mock_problem_frame",
    )


def _finish_scoping() -> ToolCallPart:
    """Call finish_scoping to continue into discovery."""
    return ToolCallPart(
        tool_name="finish_scoping",
        args=json.dumps({
            "decision": "continue_to_discovery",
            "summary": "The request is scoped clearly enough to begin WDK discovery.",
        }),
        tool_call_id="mock_finish_scoping",
    )


def _leaf_taxon() -> ToolCallPart:
    return ToolCallPart(
        tool_name="create_leaf_step",
        args=json.dumps({
            "search_name": "GenesByTaxon",
            "parameters": {"organism": '["Plasmodium falciparum 3D7"]'},
            "display_name": "P. falciparum genes",
        }),
        tool_call_id="mock_leaf_taxon",
    )


def _combine() -> ToolCallPart:
    return ToolCallPart(
        tool_name="combine_steps",
        args=json.dumps({
            "step_a_id": "1",
            "step_b_id": "2",
            "operator": "INTERSECT",
            "display_name": "Taxon AND GO term",
        }),
        tool_call_id="mock_combine",
    )


def _plan_create() -> ToolCallPart:
    return ToolCallPart(
        tool_name="create_plan",
        args=json.dumps({
            "title": "Malaria gene analysis",
            "description": "Find genes involved in malaria drug resistance",
            "rationale": "Identify candidate genes",
            "steps": [{
                "search_name": "GenesByTaxon",
                "display_name": "P. falciparum genes",
                "record_type": "transcript",
                "rationale": "All P. falciparum genes",
                "step_type": "leaf",
                "parameters": {"organism": '["Plasmodium falciparum 3D7"]'},
            }],
            "connections": [],
        }),
        tool_call_id="mock_create_plan",
    )


def _plan_submit() -> ToolCallPart:
    return ToolCallPart(
        tool_name="submit_plan",
        args=json.dumps({}),
        tool_call_id="mock_submit_plan",
    )


def _finish_discovery() -> ToolCallPart:
    """Call finish_discovery to continue into planning."""
    return ToolCallPart(
        tool_name="finish_discovery",
        args=json.dumps({
            "decision": "continue_to_planning",
            "summary": "Discovery found a usable GenesByTaxon search and enough parameter detail to plan.",
        }),
        tool_call_id="mock_finish_discovery",
    )


def _finish_planning() -> ToolCallPart:
    """Call finish_planning after submit_plan succeeds."""
    return ToolCallPart(
        tool_name="finish_planning",
        args=json.dumps({
            "decision": "present_plan",
            "summary": "The plan has been submitted for review and is ready to execute once approved.",
        }),
        tool_call_id="mock_finish_planning",
    )


def _finish_verification() -> ToolCallPart:
    """Call finish_verification to complete the turn."""
    return ToolCallPart(
        tool_name="finish_verification",
        args=json.dumps({
            "decision": "complete",
            "summary": "Verification is complete.",
        }),
        tool_call_id="mock_finish_verification",
    )


# ---------------------------------------------------------------------------
# Sequence table — data-driven, no if/elif chains
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Trigger:
    """A keyword trigger with its required tool and ordered sequence.

    Matching logic: ``keyword`` must be a substring of the (lowered) user
    text AND ``required_tool`` must be in the agent's available tools.
    Once matched, the step index (= number of ToolReturnPart messages so
    far) selects which item from ``steps`` to return.
    """

    keyword: str
    required_tool: str
    steps: list[ToolCallPart | str] = field(default_factory=list)


# Triggers are checked in order; first match wins.
_TRIGGERS: list[_Trigger] = [
    # ── Scoping phase: frame the problem before WDK discovery ──────────
    _Trigger(
        keyword="artifact graph",
        required_tool="set_problem_frame",
        steps=[_set_problem_frame(), _finish_scoping(), f"{_MOCK_PREFIX}Problem framed."],
    ),
    _Trigger(
        keyword="delegation",
        required_tool="set_problem_frame",
        steps=[_set_problem_frame(), _finish_scoping(), f"{_MOCK_PREFIX}Problem framed."],
    ),
    _Trigger(
        keyword="create step",
        required_tool="set_problem_frame",
        steps=[_set_problem_frame(), _finish_scoping(), f"{_MOCK_PREFIX}Problem framed."],
    ),
    # ── Discovery phase: discover searches needed by downstream phases ──
    _Trigger(
        keyword="artifact graph",
        required_tool="get_search_overview",
        steps=[_discover_taxon(), _finish_discovery(), f"{_MOCK_PREFIX}Search discovered."],
    ),
    _Trigger(
        keyword="delegation",
        required_tool="get_search_overview",
        steps=[_discover_taxon(), _finish_discovery(), f"{_MOCK_PREFIX}Search discovered."],
    ),
    _Trigger(
        keyword="create step",
        required_tool="get_search_overview",
        steps=[_discover_taxon(), _finish_discovery(), f"{_MOCK_PREFIX}Search discovered."],
    ),
    # ── Planning phase: create + submit plan ────────────────────────────
    _Trigger(
        keyword="artifact graph",
        required_tool="create_plan",
        steps=[_plan_create(), _plan_submit(), _finish_planning(), f"{_MOCK_PREFIX}Plan submitted."],
    ),
    _Trigger(
        keyword="delegation",
        required_tool="create_plan",
        steps=[_plan_create(), _plan_submit(), _finish_planning(), f"{_MOCK_PREFIX}Plan submitted."],
    ),
    _Trigger(
        keyword="create step",
        required_tool="create_plan",
        steps=[_plan_create(), _plan_submit(), _finish_planning(), f"{_MOCK_PREFIX}Plan submitted."],
    ),
    # ── Execution phase: per-step tool calls ────────────────────────────
    # The execution orchestrator generates prompts starting with
    # "Execute planned step ..." — matched by this keyword.
    _Trigger(
        keyword="execute planned step",
        required_tool="create_leaf_step",
        steps=[_leaf_taxon(), f"{_MOCK_PREFIX}Step created."],
    ),
    _Trigger(
        keyword="execute planned step",
        required_tool="combine_steps",
        steps=[_combine(), f"{_MOCK_PREFIX}Steps combined."],
    ),
    # ── Verification phase: explicitly complete the turn ────────────────
    _Trigger(
        keyword="artifact graph",
        required_tool="finish_verification",
        steps=[_finish_verification(), f"{_MOCK_PREFIX}Verification complete."],
    ),
    _Trigger(
        keyword="delegation",
        required_tool="finish_verification",
        steps=[_finish_verification(), f"{_MOCK_PREFIX}Verification complete."],
    ),
    _Trigger(
        keyword="create step",
        required_tool="finish_verification",
        steps=[_finish_verification(), f"{_MOCK_PREFIX}Verification complete."],
    ),
]


def _resolve(
    messages: list[ModelMessage],
    info: AgentInfo,
) -> ToolCallPart | str:
    """Determine the response from keyword + available tools + step index."""
    user_text = _extract_user_text(messages)
    tools = _available_tool_names(info)
    step = _count_tool_returns(messages)

    # Resumed approval flows re-enter verification without a fresh user prompt.
    # Keep the deterministic mock phase-complete in that case.
    if not user_text and "finish_verification" in tools:
        if step == 0:
            return _finish_verification()
        return f"{_MOCK_PREFIX}Verification complete."

    for trigger in _TRIGGERS:
        if trigger.keyword in user_text and trigger.required_tool in tools:
            if step < len(trigger.steps):
                return trigger.steps[step]
            # Sequence exhausted — fall through to echo.
            break

    # Default: echo the user's message with mock prefix.
    if user_text:
        return f"{_MOCK_PREFIX}{user_text}"
    return f"{_MOCK_PREFIX}Processed your request."


# ---------------------------------------------------------------------------
# FunctionModel callbacks
# ---------------------------------------------------------------------------


def _mock_function(
    messages: list[ModelMessage],
    info: AgentInfo,
) -> ModelResponse:
    """Phase-aware deterministic mock (non-streaming)."""
    response = _resolve(messages, info)
    if isinstance(response, ToolCallPart):
        return ModelResponse(parts=[response])
    return ModelResponse(parts=[TextPart(content=response)])


async def _mock_stream_function(
    messages: list[ModelMessage],
    info: AgentInfo,
) -> AsyncIterator[str | dict[int, DeltaToolCall]]:
    """Phase-aware deterministic mock (streaming).

    Special-cases the "slow" keyword to yield text character-by-character
    with delays, enabling stop-streaming E2E tests.
    """
    user_text = _extract_user_text(messages)

    # Slow mode: yield characters with delays for stop-streaming tests.
    if user_text == _SLOW_KEYWORD:
        text = f"{_MOCK_PREFIX}Processing slowly..."
        for char in text:
            yield char
            await asyncio.sleep(_SLOW_CHUNK_DELAY)
        return

    response = _resolve(messages, info)
    if isinstance(response, ToolCallPart):
        yield {
            0: DeltaToolCall(
                name=response.tool_name,
                json_args=response.args_as_json_str(),
                tool_call_id=response.tool_call_id,
            ),
        }
    else:
        yield response


def get_mock_model() -> FunctionModel:
    """Create a phase-aware FunctionModel for E2E testing."""
    return FunctionModel(
        _mock_function,
        stream_function=_mock_stream_function,
        model_name="mock/deterministic",
    )
