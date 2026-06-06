"""Sub-agent tool wrappers — invoked by the Lead Agent.

Each wrapper:
  1. Builds a focused work-order prompt from the Lead's input args.
  2. Constructs ``AgentDeps`` for the phase agent from ``LeadDeps.state``.
  3. Runs the phase agent (or runs declarative execution).
  4. Applies the typed delta back into ``LeadDeps.state`` (mutates the
     working PipelineState copy that the Lead's node will return to
     LangGraph at turn end).
  5. Returns the delta to the Lead.

The phase agents and their prompts/toolsets are unchanged from Stage 3 —
they just emit typed deltas instead of PhaseOutcome.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from langgraph.config import get_stream_writer
from pydantic import BaseModel
from pydantic_ai import AgentRunResultEvent
from pydantic_ai.messages import (
    AgentStreamEvent,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    PartEndEvent,
    RetryPromptPart,
    TextPart,
    ThinkingPart,
    ToolReturnPart,
)
from pydantic_ai.ui.vercel_ai.response_types import (
    DataChunk,
    FileChunk,
    SourceDocumentChunk,
    SourceUrlChunk,
)
from pydantic_ai.usage import RunUsage, UsageLimits

from pathfinder.ai.agents.discovery import discovery_agent
from pathfinder.ai.agents.execution import execution_agent
from pathfinder.ai.agents.planning import planning_agent
from pathfinder.ai.agents.roles import PhaseRole
from pathfinder.ai.agents.scoping import scoping_agent
from pathfinder.ai.agents.verification import verification_agent
from pathfinder.ai.graph.runtime import AgentDeps, Context
from pathfinder.ai.graph.state import PipelineState
from pathfinder.ai.graph.stream_events import (
    SubAgentStepPayload,
    ledger_update_event,
    sub_agent_step_event,
    turn_status_event,
)
from pathfinder.ai.lead.derive import derive_ledger
from pathfinder.ai.lead.intent import UserIntent
from pathfinder.ai.memory.schemas import MemoryValue
from pathfinder.ai.models.mock import (
    current_site_id,
    current_user_text,
    get_mock_model,
)
from pathfinder.ai.models.settings import (
    build_model_settings,
    to_pydantic_ai_model_name,
)
from pathfinder.platform.config import get_settings

PHASE_USAGE_LIMITS: UsageLimits = UsageLimits(
    request_limit=60,
    tool_calls_limit=60,
    total_tokens_limit=2_000_000,
)

_SUB_AGENT_BY_ROLE: dict[PhaseRole, Any] = {
    "scoping": scoping_agent,
    "discovery": discovery_agent,
    "planning": planning_agent,
    "execution": execution_agent,
    "verification": verification_agent,
}

TOOL_TO_PHASE_ROLE: dict[str, PhaseRole] = {
    "scope_problem": "scoping",
    "discover_searches": "discovery",
    "build_plan": "planning",
    "recover_failed_steps": "execution",
    "verify_strategy": "verification",
}


def _model_id_str(agent: Any) -> str:
    """The stable ``provider:model`` id baked into an agent at construction."""
    model = agent.model
    if model is None:
        return ""
    if isinstance(model, str):
        return model
    return str(model.model_id)


def _phase_default_model_id(role: PhaseRole) -> str:
    return _model_id_str(_SUB_AGENT_BY_ROLE[role])


def sub_agent_model_id(tool_name: str) -> str:
    """Model id for a sub-agent tool name. ``execute_plan`` is declarative
    (no LLM); everything else maps to the underlying phase agent's model.
    """
    if tool_name == "execute_plan":
        return "declarative:no-llm"
    role = TOOL_TO_PHASE_ROLE.get(tool_name)
    if role is None:
        return ""
    return _phase_default_model_id(role)


@dataclass
class SubAgentRunUsage:
    """Per-run usage from one sub-agent dispatch — fed back to lead_node so
    sub-agent tokens roll into the cumulative turn cost using the
    sub-agent's own model pricing (the Lead's pricing would be wrong;
    Lead is gpt-4.1, sub-agents are gpt-4.1-mini)."""

    usage: RunUsage
    model_name: str | None
    provider_name: str | None
    provider_url: str | None


@dataclass
class LeadDeps:
    """The Lead Agent's runtime context.

    Mutates ``state`` in place as sub-agent tools run; the Lead's node
    turns the final ``state`` into a langgraph state delta at turn end.
    """

    state: PipelineState
    intent: UserIntent | None
    runtime: Context
    retrieved_memories: list[MemoryValue]
    record_sub_agent_usage: Callable[[SubAgentRunUsage], None] = field(
        default=lambda _u: None,
    )


def _apply_agent_state(deps: LeadDeps, agent_deps: AgentDeps) -> None:
    deps.state.discovered_searches = dict(
        agent_deps.agent_state.discovered_searches,
    )
    deps.state.active_plan = agent_deps.agent_state.active_plan
    if agent_deps.problem_frame is not None:
        deps.state.problem_frame = agent_deps.problem_frame


def _emit_step(writer: Any, payload: SubAgentStepPayload) -> None:
    writer(
        {
            "chunk": sub_agent_step_event(payload).model_dump(
                by_alias=True,
                mode="json",
                exclude_none=True,
            ),
        },
    )


def _short(s: str, *, limit: int = 280) -> str:
    return s if len(s) <= limit else s[:limit] + "…"


def _summarize_tool_result(content: object) -> str:
    if isinstance(content, BaseModel):
        return _short(repr(content.model_dump(mode="json")))
    if isinstance(content, str):
        return _short(content)
    return _short(repr(content))


_STREAMABLE_METADATA = (DataChunk, SourceUrlChunk, SourceDocumentChunk, FileChunk)


def _forward_tool_metadata(writer: Any, metadata: object) -> None:
    """Forward a sub-agent tool's ``ToolReturn.metadata`` chunks to the
    main stream.

    Sub-agent tools (e.g. ``create_plan``) run outside the VercelAIAdapter
    that surfaces direct-agent tool metadata, so their ``DataChunk`` /
    source / file payloads would be dropped. Re-emit the same chunk shapes
    the adapter would, so artifacts (plan, gene set, graph) reach the UI.
    """
    if not isinstance(metadata, list):
        return
    for chunk in metadata:
        if isinstance(chunk, _STREAMABLE_METADATA):
            writer(
                {
                    "chunk": chunk.model_dump(
                        by_alias=True, mode="json", exclude_none=True
                    ),
                },
            )


def _forward_inner_event(
    *,
    parent_tool_call_id: str,
    writer: Any,
    inner_calls: dict[str, str],
    event: AgentStreamEvent,
) -> None:
    """Translate one inner-agent stream event into a
    ``data-sub-agent-step`` chunk for the frontend."""
    if isinstance(event, FunctionToolCallEvent):
        inner_calls[event.tool_call_id] = event.part.tool_name
        _emit_step(
            writer,
            SubAgentStepPayload(
                parent_tool_call_id=parent_tool_call_id,
                kind="tool",
                state="started",
                tool_call_id=event.tool_call_id,
                tool_name=event.part.tool_name,
                args=event.part.args_as_dict(),
            ),
        )
        return
    if isinstance(event, FunctionToolResultEvent):
        tool_name = inner_calls.get(event.tool_call_id)
        if tool_name is None:
            return
        result = event.result
        is_retry = isinstance(result, RetryPromptPart)
        if is_retry:
            content = result.content
            summary = _short(content) if isinstance(content, str) else "retry requested"
        else:
            summary = _summarize_tool_result(result.content)
        _emit_step(
            writer,
            SubAgentStepPayload(
                parent_tool_call_id=parent_tool_call_id,
                kind="tool",
                state="failed" if is_retry else "completed",
                tool_call_id=event.tool_call_id,
                tool_name=tool_name,
                result_summary=summary,
            ),
        )
        if isinstance(result, ToolReturnPart):
            _forward_tool_metadata(writer, result.metadata)
        return
    if isinstance(event, PartEndEvent):
        part = event.part
        if isinstance(part, TextPart) and part.content.strip():
            _emit_step(
                writer,
                SubAgentStepPayload(
                    parent_tool_call_id=parent_tool_call_id,
                    kind="text",
                    state="completed",
                    text=_short(part.content, limit=2000),
                ),
            )
        elif isinstance(part, ThinkingPart) and part.content.strip():
            _emit_step(
                writer,
                SubAgentStepPayload(
                    parent_tool_call_id=parent_tool_call_id,
                    kind="reasoning",
                    state="completed",
                    text=_short(part.content, limit=2000),
                ),
            )


def _phase_override_kwargs(
    runtime: Context,
    role: PhaseRole,
) -> dict[str, Any]:
    """Resolve the effective model + provider settings for a phase run.

    Always overrides: the effective model (user pick, else the phase default)
    is translated to its pydantic-ai name and paired with provider-correct
    settings (caching + reasoning effort), so caching is applied on every run.
    """
    if get_settings().pathfinder_chat_provider.strip().lower() == "mock":
        return {"model": get_mock_model()}
    effective_model = runtime.phase_models.get(role) or _phase_default_model_id(role)
    effort = runtime.phase_reasoning.get(role)
    return {
        "model": to_pydantic_ai_model_name(effective_model),
        "model_settings": build_model_settings(effective_model, thinking=effort),
    }


_PHASE_STATUS_LABELS: dict[PhaseRole, str] = {
    "lead": "Thinking...",
    "scoping": "Scoping the problem...",
    "discovery": "Finding searches...",
    "planning": "Building a plan...",
    "execution": "Recovering failed steps...",
    "verification": "Verifying the strategy...",
}


async def _stream_sub_agent[OutputT: BaseModel](
    *,
    role: PhaseRole,
    work_order: str,
    agent_deps: AgentDeps,
    parent_tool_call_id: str,
    expected_output_type: type[OutputT],
    deps: LeadDeps,
) -> OutputT | None:
    agent = _SUB_AGENT_BY_ROLE[role]
    """Run a sub-agent, forward its inner events as
    ``data-sub-agent-step`` chunks, push its usage into the Lead's
    accumulator (using the sub-agent's own model for cost attribution),
    and return the typed delta."""
    writer = get_stream_writer()
    inner_calls: dict[str, str] = {}
    output: OutputT | None = None
    usage = RunUsage()
    # Let the deterministic mock target a site-valid search/organism and
    # branch the canned plan on what the user asked for.
    current_site_id.set(deps.runtime.site_id)
    current_user_text.set(deps.state.user_prompt)
    override_kwargs = _phase_override_kwargs(deps.runtime, role)
    override_ctx = (
        agent.override(**override_kwargs)
        if override_kwargs
        else contextlib.nullcontext()
    )
    writer(
        {
            "chunk": turn_status_event(
                label=_PHASE_STATUS_LABELS.get(role, "Working..."),
                waiting_on_llm=True,
            ).model_dump(by_alias=True, mode="json", exclude_none=True),
        },
    )
    with override_ctx:
        async for event in agent.run_stream_events(
            work_order,
            deps=agent_deps,
            usage_limits=PHASE_USAGE_LIMITS,
            usage=usage,
        ):
            if isinstance(event, AgentRunResultEvent):
                agent_output = event.result.output
                if isinstance(agent_output, expected_output_type):
                    output = agent_output
                response = event.result.response
                deps.record_sub_agent_usage(
                    SubAgentRunUsage(
                        usage=event.result.usage,
                        model_name=response.model_name,
                        provider_name=response.provider_name,
                        provider_url=response.provider_url,
                    ),
                )
                continue
            _forward_inner_event(
                parent_tool_call_id=parent_tool_call_id,
                writer=writer,
                inner_calls=inner_calls,
                event=event,
            )
            if isinstance(event, FunctionToolResultEvent):
                _emit_live_ledger(writer, deps, agent_deps)
    return output


def _emit_live_ledger(
    writer: Any,
    deps: LeadDeps,
    agent_deps: AgentDeps,
) -> None:
    """After every sub-agent tool call, sync state and broadcast a fresh
    ledger snapshot so the UI sees discovery decisions, plan edits, etc. as
    they happen instead of waiting for the sub-agent to return to the Lead.
    """
    _apply_agent_state(deps, agent_deps)
    ledger = derive_ledger(deps.state, deps.intent)
    writer(
        {
            "chunk": ledger_update_event(ledger=ledger).model_dump(
                by_alias=True,
                mode="json",
                exclude_none=True,
            ),
        },
    )
