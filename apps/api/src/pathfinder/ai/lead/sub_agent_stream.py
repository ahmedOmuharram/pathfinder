"""The sub-agent streaming engine.

Runs one phase agent, renders its inner events onto the chat stream, and
surfaces an approval-required tool call as a tool part the user can answer.
"""

from __future__ import annotations

import contextlib
import json
from dataclasses import dataclass
from typing import Any, Literal

from assistant_core.cost import cost_for_run
from assistant_core.graph.emit import emit_chunk
from assistant_core.graph.stream_events import (
    SubAgentCallPayload,
    SubAgentStepPayload,
    sub_agent_call_event,
    sub_agent_step_event,
    turn_status_event,
)
from assistant_core.graph.turn_state import (
    SubAgentApprovalCall,
    SubAgentApprovalPending,
)
from assistant_core.models.scripted import (
    current_scope_id,
    current_user_text,
)
from assistant_core.platform.logging import get_logger
from langgraph.config import get_stream_writer
from pydantic import BaseModel
from pydantic_ai import AgentRunResultEvent
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.messages import (
    AgentStreamEvent,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    ModelMessage,
    ModelMessagesTypeAdapter,
    PartEndEvent,
    RetryPromptPart,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.tools import DeferredToolRequests, DeferredToolResults
from pydantic_ai.ui.vercel_ai.response_types import (
    DataChunk,
    FileChunk,
    SourceDocumentChunk,
    SourceUrlChunk,
    ToolApprovalRequestChunk,
    ToolInputAvailableChunk,
    ToolInputStartChunk,
    ToolOutputAvailableChunk,
    ToolOutputDeniedChunk,
)
from pydantic_ai.usage import RunUsage

from pathfinder.ai.agents.roles import PhaseRole
from pathfinder.ai.capabilities.error_classification import is_error_directive
from pathfinder.ai.graph._llm_capture import maybe_wrap_model
from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.graph.stream_events import ledger_update_event
from pathfinder.ai.lead.derive import derive_ledger
from pathfinder.ai.lead.sub_agent_tools import (
    SUB_AGENT_BY_ROLE,
    LeadDeps,
    SubAgentRunUsage,
    apply_agent_state,
    phase_default_model_id,
    phase_override_kwargs,
    phase_usage_limits,
)

logger = get_logger(__name__)

_RESULT_LIMIT = 8000

_STREAMABLE_METADATA = (DataChunk, SourceUrlChunk, SourceDocumentChunk, FileChunk)

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


@dataclass(frozen=True)
class SubAgentResume:
    """Re-entry into a sub-agent run that stopped at an approval."""

    messages: list[ModelMessage]
    results: DeferredToolResults


@dataclass(frozen=True)
class SubAgentApprovalWait:
    """A sub-agent run waiting on the user's answer to a tool approval."""

    pending: SubAgentApprovalPending


def _emit_step(writer: Any, payload: SubAgentStepPayload) -> None:
    emit_chunk(writer, sub_agent_step_event(payload))


def _short(s: str, *, limit: int = 280) -> str:
    return s if len(s) <= limit else s[:limit] + "..."


def _summarize_tool_result(content: object) -> str:
    if isinstance(content, BaseModel):
        return _short(json.dumps(content.model_dump(mode="json")), limit=_RESULT_LIMIT)
    if isinstance(content, str):
        return _short(content, limit=_RESULT_LIMIT)
    try:
        return _short(json.dumps(content), limit=_RESULT_LIMIT)
    except TypeError, ValueError:
        return _short(str(content), limit=_RESULT_LIMIT)


def _result_summary(result: ToolReturnPart | RetryPromptPart) -> str:
    """One-line rendering of an inner tool's result."""
    if isinstance(result, RetryPromptPart):
        content = result.content
        return _short(
            content if isinstance(content, str) else result.model_response(),
            limit=_RESULT_LIMIT,
        )
    return _summarize_tool_result(result.content)


def _step_state(
    result: ToolReturnPart | RetryPromptPart,
) -> Literal["completed", "failed", "denied"]:
    """Terminal state of one inner tool call. A denial is the user's decision,
    not a failure."""
    if isinstance(result, RetryPromptPart):
        return "failed"
    if result.outcome == "denied":
        return "denied"
    return "failed" if is_error_directive(result.content) else "completed"


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
            emit_chunk(writer, chunk)


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
        _emit_step(
            writer,
            SubAgentStepPayload(
                parent_tool_call_id=parent_tool_call_id,
                kind="tool",
                state=_step_state(result),
                tool_call_id=event.tool_call_id,
                tool_name=tool_name,
                result_summary=_result_summary(result),
            ),
        )
        if isinstance(result, ToolReturnPart):
            _forward_tool_metadata(writer, result.metadata)
        return
    if isinstance(event, PartEndEvent):
        part = event.part
        if not isinstance(part, (TextPart, ThinkingPart)) or not part.content.strip():
            return
        _emit_step(
            writer,
            SubAgentStepPayload(
                parent_tool_call_id=parent_tool_call_id,
                kind="text" if isinstance(part, TextPart) else "reasoning",
                state="completed",
                text=_short(part.content, limit=2000),
            ),
        )


def _announce_approval(writer: Any, call: ToolCallPart) -> SubAgentApprovalCall:
    """Render one inner tool call as a tool part awaiting the user's answer."""
    args = call.args_as_dict()
    emit_chunk(
        writer,
        ToolInputStartChunk(tool_call_id=call.tool_call_id, tool_name=call.tool_name),
    )
    emit_chunk(
        writer,
        ToolInputAvailableChunk(
            tool_call_id=call.tool_call_id,
            tool_name=call.tool_name,
            input=args,
        ),
    )
    emit_chunk(
        writer,
        ToolApprovalRequestChunk(
            approval_id=call.tool_call_id,
            tool_call_id=call.tool_call_id,
        ),
    )
    return SubAgentApprovalCall(
        tool_call_id=call.tool_call_id,
        tool_name=call.tool_name,
        args=args,
    )


def _await_approval(
    *,
    writer: Any,
    role: PhaseRole,
    requests: DeferredToolRequests,
    messages: list[ModelMessage],
) -> SubAgentApprovalWait | None:
    """Ask the user about every approval the sub-agent run stopped at."""
    if not requests.approvals:
        return None
    return SubAgentApprovalWait(
        pending=SubAgentApprovalPending(
            role=role,
            approvals=[_announce_approval(writer, call) for call in requests.approvals],
            messages_json=ModelMessagesTypeAdapter.dump_json(messages).decode(),
        ),
    )


def _close_answered_approval(
    writer: Any,
    event: FunctionToolResultEvent,
    answered: frozenset[str],
) -> None:
    """Put an answered tool part into its terminal state on the client."""
    if event.tool_call_id not in answered:
        return
    result = event.part
    if isinstance(result, ToolReturnPart) and result.outcome == "denied":
        emit_chunk(writer, ToolOutputDeniedChunk(tool_call_id=event.tool_call_id))
        return
    emit_chunk(
        writer,
        ToolOutputAvailableChunk(
            tool_call_id=event.tool_call_id,
            output=_result_summary(result),
        ),
    )


async def stream_sub_agent[OutputT: BaseModel](
    *,
    run: PhaseRun,
    agent_deps: AgentDeps,
    parent_tool_call_id: str,
    expected_output_type: type[OutputT],
    deps: LeadDeps,
    resume: SubAgentResume | None = None,
) -> OutputT | SubAgentApprovalWait | None:
    """Run a sub-agent, forward its inner events, and return the typed delta.

    Answers a ``resume`` into the run that produced it. Returns a
    ``SubAgentApprovalWait`` when the run stops on a tool the user must
    approve, and ``None`` when the run exhausts its budget.
    """
    role = run.role
    agent = SUB_AGENT_BY_ROLE[role]
    writer = get_stream_writer()
    inner_calls: dict[str, str] = {}
    answered: frozenset[str] = (
        frozenset(resume.results.approvals) if resume is not None else frozenset()
    )
    output: OutputT | None = None
    wait: SubAgentApprovalWait | None = None
    usage = RunUsage()
    # The mock model reads these to pick a site-valid search and branch its
    # canned plan.
    current_scope_id.set(deps.runtime.site_id)
    current_user_text.set(deps.state.user_prompt)
    override_kwargs = phase_override_kwargs(deps.runtime, role)
    if "model" in override_kwargs:
        override_kwargs["model"] = maybe_wrap_model(override_kwargs["model"], role)
    override_ctx = (
        agent.override(**override_kwargs)
        if override_kwargs
        else contextlib.nullcontext()
    )
    emit_chunk(
        writer,
        turn_status_event(
            label=_PHASE_STATUS_LABELS.get(role, "Working..."),
            waiting_on_llm=True,
        ),
    )
    with override_ctx:
        try:
            async with agent.run_stream_events(
                run.work_order if resume is None else None,
                deps=agent_deps,
                message_history=resume.messages if resume is not None else None,
                deferred_tool_results=resume.results if resume is not None else None,
                usage_limits=phase_usage_limits(run.declared_criteria),
                usage=usage,
            ) as events:
                async for event in events:
                    if isinstance(event, AgentRunResultEvent):
                        agent_output = event.result.output
                        if isinstance(agent_output, expected_output_type):
                            output = agent_output
                        elif isinstance(agent_output, DeferredToolRequests):
                            wait = _await_approval(
                                writer=writer,
                                role=role,
                                requests=agent_output,
                                messages=list(event.result.all_messages()),
                            )
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
                        _close_answered_approval(writer, event, answered)
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
    return wait if wait is not None else output


def _emit_running_sub_agent_usage(
    writer: Any,
    role: PhaseRole,
    parent_tool_call_id: str,
    usage: RunUsage,
) -> None:
    """Push the sub-agent's running tokens/cost after each inner tool call."""
    model_id = phase_default_model_id(role)
    provider, _, model = model_id.partition(":")
    cost = cost_for_run(
        usage=usage,
        model_name=model or None,
        provider_name=provider or None,
        provider_url=None,
    )
    emit_chunk(
        writer,
        sub_agent_call_event(
            SubAgentCallPayload(
                tool_call_id=parent_tool_call_id,
                sub_agent=role,
                phase=role,
                state="started",
                model_id=model_id,
                tokens=usage.total_tokens,
                cost_usd=str(cost),
            )
        ),
    )


def _emit_live_ledger(
    writer: Any,
    deps: LeadDeps,
    agent_deps: AgentDeps,
) -> None:
    """Sync state and broadcast a ledger snapshot after a sub-agent tool call."""
    apply_agent_state(deps, agent_deps)
    ledger = derive_ledger(deps.state, deps.intent)
    emit_chunk(writer, ledger_update_event(ledger=ledger))
