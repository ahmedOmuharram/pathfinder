"""Sub-agent event handling for the Lead node.

Translates the Lead's inner stream events into ``data-sub-agent-call``
cards + ledger refreshes, and the summarization helpers behind them.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel
from pydantic_ai.messages import (
    AgentStreamEvent,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    RetryPromptPart,
    ToolReturnPart,
)
from pydantic_ai.ui.vercel_ai.response_types import (
    BaseChunk,
    ToolApprovalRequestChunk,
    ToolInputAvailableChunk,
    ToolInputDeltaChunk,
    ToolInputErrorChunk,
    ToolInputStartChunk,
    ToolOutputAvailableChunk,
    ToolOutputDeniedChunk,
    ToolOutputErrorChunk,
)

from pathfinder.ai.graph._lead_capture import _emit_chunk
from pathfinder.ai.graph.stream_events import (
    SubAgentCallPayload,
    ledger_update_event,
    sub_agent_call_event,
)
from pathfinder.ai.lead.derive import derive_ledger
from pathfinder.ai.lead.sub_agent_tools import LeadDeps, sub_agent_model_id

_SUB_AGENT_TOOL_TO_PHASE: dict[str, str] = {
    "frame_problem": "frame",
    "build_strategy": "build",
    "recover_failed_steps": "build",
    "verify_strategy": "verification",
}
_SUB_AGENT_TOOL_NAMES = frozenset(_SUB_AGENT_TOOL_TO_PHASE.keys())

# Every chunk that names a tool call, and so must follow that call's rendering.
# Suppression is keyed on WHAT a chunk refers to rather than on a remembered
# list of types: ``ToolOutputErrorChunk`` was absent from the old list because
# it only appears when a run raises, and the resulting orphan crashed the turn.
# ``test_every_tool_chunk_type_is_classified`` fails if pydantic-ai adds one
# nobody classified.
_TOOL_CALL_CHUNKS = (
    ToolInputStartChunk,
    ToolInputDeltaChunk,
    ToolInputAvailableChunk,
    ToolInputErrorChunk,
    ToolOutputAvailableChunk,
    ToolOutputErrorChunk,
)

# Deliberately NOT suppressed: an approval question the user never sees is a
# turn that waits forever. No sub-agent dispatch is gated on approval today,
# so this costs nothing and keeps the failure mode obvious if one ever is.
_CHUNKS_EXEMPT_FROM_SUPPRESSION = (
    ToolApprovalRequestChunk,
    ToolOutputDeniedChunk,
)

_NAMED_SUB_AGENT_CHUNKS = (
    ToolInputStartChunk,
    ToolInputAvailableChunk,
    ToolInputErrorChunk,
)


def is_suppressed_sub_agent_chunk(
    chunk: BaseChunk,
    sub_agent_tool_calls: dict[str, str],
) -> bool:
    """Hide the native tool chunks for a sub-agent dispatch so the rich
    ``data-sub-agent-call`` card is the only inline rendering.

    Classifies a dispatch from ``tool_name`` on its first chunk and primes
    ``sub_agent_tool_calls``. The raw input chunks stream from the model's
    part events *before* ``FunctionToolCallEvent`` records the id, so keying
    only off the recorded id leaks them — the raw tool card renders and hangs
    on "Running" because its later output chunk *is* suppressed.

    This has to hold on the failure path too. When a run raises, pydantic-ai
    closes each pending tool call with a tool output; for a dispatch, that
    output names a call the client was never shown, and the AI SDK throws
    ``UIMessageStreamError`` and fails the entire response.
    """
    if isinstance(chunk, _CHUNKS_EXEMPT_FROM_SUPPRESSION):
        return False
    if not isinstance(chunk, _TOOL_CALL_CHUNKS):
        return False
    if (
        isinstance(chunk, _NAMED_SUB_AGENT_CHUNKS)
        and chunk.tool_name in _SUB_AGENT_TOOL_NAMES
    ):
        sub_agent_tool_calls[chunk.tool_call_id] = chunk.tool_name
        return True
    return chunk.tool_call_id in sub_agent_tool_calls


def _truncate_summary(text: str, limit: int = 280) -> str:
    """Cut to ``limit`` chars on a word boundary, appending ASCII ``...``."""
    if len(text) <= limit:
        return text
    cut = text[: limit - 3].rstrip()
    boundary = cut.rfind(" ")
    if boundary > 0:
        cut = cut[:boundary].rstrip()
    return f"{cut}..."


def _summarize_sub_agent_call_args(args: dict[str, Any]) -> str:
    """One-line input summary for the SubAgentCallCard 'started' state."""
    reason = args.get("reason")
    if isinstance(reason, str) and reason:
        return _truncate_summary(reason)
    return ""


def _summarize_sub_agent_result(result: ToolReturnPart) -> str:
    """One-line result summary for the SubAgentCallCard 'completed' state."""
    content = result.content
    if isinstance(content, BaseModel):
        return _summarize_delta(content)
    if isinstance(content, dict):
        return _summarize_delta_dict(content)
    return _truncate_summary(str(content))


def _summarize_delta(delta: BaseModel) -> str:
    return _summarize_delta_dict(delta.model_dump())


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def _summarize_outcome(outcome: dict[str, Any]) -> str:
    built = len(outcome.get("pushed_step_ids") or [])
    failed = len(outcome.get("failed_steps") or [])
    if failed > 0:
        return f"Built {built}, {failed} failed"
    return f"Built {_plural(built, 'step')}"


def _summarize_delta_dict(data: dict[str, Any]) -> str:
    """Compact, human-readable one-liner from a sub-agent's typed delta."""
    if "disposition" in data:
        disposition = data.get("disposition")
        if disposition == "needs_user":
            return _plural(len(data.get("open_questions") or []), "open question")
        return _truncate_summary(str(data.get("summary") or "Framed"))
    if "actions_taken" in data:
        return _plural(len(data.get("actions_taken") or []), "recovery action")
    if "outcome" in data:
        return _summarize_outcome(data.get("outcome") or {})
    if "digest" in data:
        success = (data.get("digest") or {}).get("success", False)
        return "Verified successfully" if success else "Issues found"
    return ""


def sub_agent_result_failed(result: ToolReturnPart | RetryPromptPart) -> bool:
    """Whether a sub-agent dispatch ended badly.

    Two shapes mean failure and only one is obvious. A ``RetryPromptPart`` is
    the sub-agent asking to be re-run. The other is pydantic-ai closing a
    pending tool call when the run raises: it synthesizes a ``ToolReturnPart``
    with ``outcome="failed"`` and the content "Tool execution was interrupted
    by an error." Reading only the retry case rendered an interrupted sub-agent
    as "completed" -- a false success, which is worse than the crash that
    suppressing its orphan chunk removed.
    """
    if isinstance(result, RetryPromptPart):
        return True
    return result.outcome == "failed"


def handle_sub_agent_event(
    deps: LeadDeps,
    writer: Any,
    event: AgentStreamEvent,
    sub_agent_tool_calls: dict[str, str],
    sub_agent_usage: dict[str, tuple[int, str]],
) -> None:
    """Emit ``data-sub-agent-call`` (started/completed/failed) and refresh
    the Ledger when a sub-agent tool runs.

    ``sub_agent_tool_calls`` maps tool_call_id → tool_name for the calls
    we've classified as sub-agents; the chunk-emission loop reads it to
    suppress the default tool-input/output chunks for those calls.
    """
    if isinstance(event, FunctionToolCallEvent):
        tool_name = event.part.tool_name
        if tool_name not in _SUB_AGENT_TOOL_NAMES:
            return
        sub_agent_tool_calls[event.tool_call_id] = tool_name
        _emit_chunk(
            writer,
            sub_agent_call_event(
                SubAgentCallPayload(
                    tool_call_id=event.tool_call_id,
                    sub_agent=tool_name,
                    phase=_SUB_AGENT_TOOL_TO_PHASE[tool_name],
                    state="started",
                    model_id=sub_agent_model_id(tool_name),
                    summary=_summarize_sub_agent_call_args(event.part.args_as_dict()),
                )
            ),
        )
        return
    if isinstance(event, FunctionToolResultEvent):
        result_tool_name = sub_agent_tool_calls.get(event.tool_call_id)
        if result_tool_name is None:
            return
        result = event.part
        if isinstance(result, RetryPromptPart):
            content = result.content
            summary = (
                _truncate_summary(content)
                if isinstance(content, str)
                else "retry requested"
            )
        else:
            summary = _summarize_sub_agent_result(result)
        failed = sub_agent_result_failed(result)
        tokens, cost_usd = sub_agent_usage.get(event.tool_call_id, (0, "0"))
        _emit_chunk(
            writer,
            sub_agent_call_event(
                SubAgentCallPayload(
                    tool_call_id=event.tool_call_id,
                    sub_agent=result_tool_name,
                    phase=_SUB_AGENT_TOOL_TO_PHASE[result_tool_name],
                    state="failed" if failed else "completed",
                    model_id=sub_agent_model_id(result_tool_name),
                    summary=summary,
                    succeeded=not failed,
                    tokens=tokens,
                    cost_usd=cost_usd,
                )
            ),
        )
        ledger = derive_ledger(deps.state, deps.intent)
        _emit_chunk(writer, ledger_update_event(ledger=ledger))
