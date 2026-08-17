"""Sub-agent tool wrappers that the Lead Agent calls.

Each wrapper runs one phase agent and applies its typed delta into the
working ``PipelineState`` that the Lead's node returns at turn end.
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from langgraph.config import get_stream_writer
from pydantic import BaseModel
from pydantic_ai import AgentRunResultEvent
from pydantic_ai.exceptions import UsageLimitExceeded
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

from pathfinder.ai.agents.execution import execution_agent
from pathfinder.ai.agents.frame import frame_agent
from pathfinder.ai.agents.roles import PhaseRole
from pathfinder.ai.agents.verification import verification_agent
from pathfinder.ai.capabilities.error_classification import is_error_directive
from pathfinder.ai.cost import cost_for_run
from pathfinder.ai.graph._llm_capture import maybe_wrap_model
from pathfinder.ai.graph.runtime import AgentDeps, Context
from pathfinder.ai.graph.state import PipelineState
from pathfinder.ai.graph.stream_events import (
    SubAgentCallPayload,
    SubAgentStepPayload,
    ledger_update_event,
    sub_agent_call_event,
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
from pathfinder.ai.models.settings import build_model_settings
from pathfinder.ai.models.tiers import PhaseTierConfig, resolve_phase_tier_config
from pathfinder.platform.config import get_settings
from pathfinder.platform.logging import get_logger

logger = get_logger(__name__)

# Binding one criterion costs about seven calls: find a search, read it, read a
# parameter or two, set the criterion. Reading the ledger and setting the
# structure are paid once for the pass.
CALLS_PER_CRITERION = 7
STRUCTURE_CALLS = 8
# A pass below the floor cannot recover from a single wrong search. The cap is
# what stops an overstated count from spending a whole turn.
MIN_PHASE_TOOL_CALLS = 40
MAX_PHASE_TOOL_CALLS = 160
_PHASE_TOKEN_LIMIT = 2_000_000


def phase_usage_limits(declared_criteria: int) -> UsageLimits:
    """The ceiling for one sub-agent pass over ``declared_criteria`` criteria."""
    wanted = declared_criteria * CALLS_PER_CRITERION + STRUCTURE_CALLS
    calls = max(MIN_PHASE_TOOL_CALLS, min(MAX_PHASE_TOOL_CALLS, wanted))
    return UsageLimits(
        request_limit=calls,
        tool_calls_limit=calls,
        total_tokens_limit=_PHASE_TOKEN_LIMIT,
    )

_SUB_AGENT_BY_ROLE: dict[PhaseRole, Any] = {
    "frame": frame_agent,
    "execution": execution_agent,
    "verification": verification_agent,
}

TOOL_TO_PHASE_ROLE: dict[str, PhaseRole] = {
    "frame_problem": "frame",
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
    """The phase's model when the user pinned nothing: the configured
    ``(default_provider, default_tier)`` preset, else the agent's baked model."""
    cfg = _configured_tier_config(role)
    if cfg is not None:
        return cfg.model_id
    return _model_id_str(_SUB_AGENT_BY_ROLE[role])


def _configured_tier_config(role: PhaseRole) -> PhaseTierConfig | None:
    settings = get_settings()
    return resolve_phase_tier_config(
        settings.default_provider, settings.default_tier, role
    )


def sub_agent_model_id(tool_name: str) -> str:
    """Model id for a sub-agent tool name. ``build_strategy`` is declarative
    (no LLM); everything else maps to the underlying phase agent's model.
    """
    if tool_name == "build_strategy":
        return "declarative:no-llm"
    role = TOOL_TO_PHASE_ROLE.get(tool_name)
    if role is None:
        return ""
    return _phase_default_model_id(role)


@dataclass
class SubAgentRunUsage:
    """Usage from one sub-agent dispatch.

    Each phase can run a different model, so the cost uses the sub-agent's
    own model pricing, not the Lead's.
    """

    usage: RunUsage
    model_name: str | None
    provider_name: str | None
    provider_url: str | None
    parent_tool_call_id: str


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
    draft = agent_deps.agent_state.operational_spec_draft
    if draft.criteria or draft.dropped:
        deps.state.operational_spec = draft


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
    return s if len(s) <= limit else s[:limit] + "..."


_RESULT_LIMIT = 8000


def _summarize_tool_result(content: object) -> str:
    if isinstance(content, BaseModel):
        return _short(json.dumps(content.model_dump(mode="json")), limit=_RESULT_LIMIT)
    if isinstance(content, str):
        return _short(content, limit=_RESULT_LIMIT)
    try:
        return _short(json.dumps(content), limit=_RESULT_LIMIT)
    except TypeError, ValueError:
        return _short(str(content), limit=_RESULT_LIMIT)


_STREAMABLE_METADATA = (DataChunk, SourceUrlChunk, SourceDocumentChunk, FileChunk)


def _forward_tool_metadata(writer: Any, metadata: object) -> None:
    """Forward a sub-agent tool's ``ToolReturn.metadata`` chunks to the
    main stream.

    A sub-agent tool runs outside the VercelAIAdapter, so the adapter does
    not emit these chunks.
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
        result = event.part
        if isinstance(result, RetryPromptPart):
            content = result.content
            summary = _short(
                content if isinstance(content, str) else result.model_response(),
                limit=_RESULT_LIMIT,
            )
            failed = True
        else:
            summary = _summarize_tool_result(result.content)
            failed = is_error_directive(result.content)
        _emit_step(
            writer,
            SubAgentStepPayload(
                parent_tool_call_id=parent_tool_call_id,
                kind="tool",
                state="failed" if failed else "completed",
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
    """Resolve the model and the provider settings for a phase run.

    The model is the user pick, else the phase default. Settings always
    accompany it, because caching is provider specific.
    """
    if get_settings().pathfinder_chat_provider.strip().lower() == "mock":
        return {"model": get_mock_model()}
    effective_model = runtime.phase_models.get(role) or _phase_default_model_id(role)
    tier_cfg = _configured_tier_config(role)
    effort = runtime.phase_reasoning.get(role) or (
        tier_cfg.reasoning_effort if tier_cfg is not None else None
    )
    return {
        "model": effective_model,
        "model_settings": build_model_settings(effective_model, thinking=effort),
    }


_PHASE_STATUS_LABELS: dict[PhaseRole, str] = {
    "lead": "Thinking...",
    "frame": "Framing the strategy...",
    "execution": "Recovering failed steps...",
    "verification": "Verifying the strategy...",
}


@dataclass(frozen=True)
class PhaseRun:
    """What to run: which sub-agent, on what, at what size."""

    role: PhaseRole
    work_order: str
    declared_criteria: int = 0


async def _stream_sub_agent[OutputT: BaseModel](
    *,
    run: PhaseRun,
    agent_deps: AgentDeps,
    parent_tool_call_id: str,
    expected_output_type: type[OutputT],
    deps: LeadDeps,
) -> OutputT | None:
    role = run.role
    work_order = run.work_order
    agent = _SUB_AGENT_BY_ROLE[role]
    """Run a sub-agent, forward its inner events, and return the typed delta."""
    writer = get_stream_writer()
    inner_calls: dict[str, str] = {}
    output: OutputT | None = None
    usage = RunUsage()
    # The mock model reads these to pick a site-valid search and branch its
    # canned plan.
    current_site_id.set(deps.runtime.site_id)
    current_user_text.set(deps.state.user_prompt)
    override_kwargs = _phase_override_kwargs(deps.runtime, role)
    if "model" in override_kwargs:
        override_kwargs["model"] = maybe_wrap_model(override_kwargs["model"], role)
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
        try:
            async with agent.run_stream_events(
                work_order,
                deps=agent_deps,
                usage_limits=phase_usage_limits(run.declared_criteria),
                usage=usage,
            ) as events:
                async for event in events:
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
                                parent_tool_call_id=parent_tool_call_id,
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
                        _emit_running_sub_agent_usage(
                            writer, role, parent_tool_call_id, usage
                        )
        except UsageLimitExceeded as exc:
            # A usage ceiling is a budget, not a correctness failure. The
            # sub-agent writes each result into the shared draft as it goes,
            # so the Lead reads the partial draft.
            logger.warning(
                "sub-agent hit its usage ceiling; keeping partial progress",
                role=role,
                error=str(exc),
            )
            return None
    return output


def _emit_running_sub_agent_usage(
    writer: Any,
    role: PhaseRole,
    parent_tool_call_id: str,
    usage: RunUsage,
) -> None:
    """Push the sub-agent's running tokens/cost after each inner tool call."""
    model_id = _phase_default_model_id(role)
    provider, _, model = model_id.partition(":")
    cost = cost_for_run(
        usage=usage,
        model_name=model or None,
        provider_name=provider or None,
        provider_url=None,
    )
    writer(
        {
            "chunk": sub_agent_call_event(
                SubAgentCallPayload(
                    tool_call_id=parent_tool_call_id,
                    sub_agent=role,
                    phase=role,
                    state="started",
                    model_id=model_id,
                    tokens=usage.total_tokens,
                    cost_usd=str(cost),
                )
            ).model_dump(by_alias=True, mode="json", exclude_none=True),
        },
    )


def _emit_live_ledger(
    writer: Any,
    deps: LeadDeps,
    agent_deps: AgentDeps,
) -> None:
    """Sync state and broadcast a ledger snapshot after a sub-agent tool call."""
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
