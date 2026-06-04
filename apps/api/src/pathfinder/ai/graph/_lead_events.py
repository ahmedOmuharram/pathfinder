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
from pydantic_ai.ui.vercel_ai.response_types import BaseChunk

from pathfinder.ai.graph._lead_capture import _emit_chunk
from pathfinder.ai.graph.stream_events import (
    SubAgentCallPayload,
    ledger_update_event,
    sub_agent_call_event,
)
from pathfinder.ai.lead.derive import derive_ledger
from pathfinder.ai.lead.sub_agent_tools import LeadDeps, sub_agent_model_id

_SUB_AGENT_TOOL_TO_PHASE: dict[str, str] = {
    "scope_problem": "scoping",
    "discover_searches": "discovery",
    "build_plan": "planning",
    "execute_plan": "execution",
    "recover_failed_steps": "execution",
    "verify_strategy": "verification",
}
_SUB_AGENT_TOOL_NAMES = frozenset(_SUB_AGENT_TOOL_TO_PHASE.keys())

_SUPPRESSED_SUB_AGENT_CHUNK_TYPES = frozenset(
    {
        "tool-input-start",
        "tool-input-delta",
        "tool-input-available",
        "tool-output-available",
        "tool-input-error",
    }
)


def is_suppressed_sub_agent_chunk(
    chunk: BaseChunk,
    sub_agent_tool_calls: dict[str, str],
) -> bool:
    """Hide the default tool-input/output chunks for sub-agent calls so
    the rich ``data-sub-agent-call`` card is the only inline rendering."""
    chunk_type = getattr(chunk, "type", None)
    if chunk_type not in _SUPPRESSED_SUB_AGENT_CHUNK_TYPES:
        return False
    tool_call_id = getattr(chunk, "tool_call_id", None)
    if not isinstance(tool_call_id, str):
        return False
    return tool_call_id in sub_agent_tool_calls


def _summarize_sub_agent_call_args(args: dict[str, Any]) -> str:
    """One-line input summary for the SubAgentCallCard 'started' state."""
    reason = args.get("reason")
    intent_summary = args.get("intent_summary")
    hints = args.get("hints")
    parts: list[str] = []
    if isinstance(reason, str) and reason:
        parts.append(reason)
    if isinstance(intent_summary, str) and intent_summary:
        parts.append(f"intent: {intent_summary}")
    if isinstance(hints, str) and hints:
        parts.append(f"hints: {hints}")
    return " · ".join(parts)[:280]


def _summarize_sub_agent_result(result: ToolReturnPart) -> str:
    """One-line result summary for the SubAgentCallCard 'completed' state."""
    content = result.content
    if isinstance(content, BaseModel):
        return _summarize_delta(content)
    if isinstance(content, dict):
        return _summarize_delta_dict(content)
    return str(content)[:280]


def _summarize_delta(delta: BaseModel) -> str:
    return _summarize_delta_dict(delta.model_dump())


def _summarize_delta_dict(data: dict[str, Any]) -> str:
    """Compact one-liner from a sub-agent's typed delta payload."""
    if "frame" in data:
        frame = data.get("frame") or {}
        return (
            f"frame ready={frame.get('ready_for_wdk_discovery', False)} "
            f"questions={len(frame.get('blocking_questions', []))}"
        )
    if "selections" in data or "fit_reports" in data:
        sels = data.get("selections") or {}
        return f"selected {len(sels)} searches"
    if "plan" in data:
        plan = data.get("plan") or {}
        steps = plan.get("steps") or []
        return f"plan with {len(steps)} step(s)"
    if "outcome" in data:
        outcome = data.get("outcome") or {}
        return (
            f"pushed={len(outcome.get('pushed_step_ids') or [])} "
            f"failed={len(outcome.get('failed_steps') or [])}"
        )
    if "digest" in data:
        digest = data.get("digest") or {}
        return f"verification success={digest.get('success', False)}"
    return ""


def handle_sub_agent_event(
    deps: LeadDeps,
    writer: Any,
    event: AgentStreamEvent,
    sub_agent_tool_calls: dict[str, str],
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
        result = event.result
        if isinstance(result, RetryPromptPart):
            content = result.content
            summary = content[:280] if isinstance(content, str) else "retry requested"
            is_retry = True
        else:
            summary = _summarize_sub_agent_result(result)
            is_retry = False
        _emit_chunk(
            writer,
            sub_agent_call_event(
                SubAgentCallPayload(
                    tool_call_id=event.tool_call_id,
                    sub_agent=result_tool_name,
                    phase=_SUB_AGENT_TOOL_TO_PHASE[result_tool_name],
                    state="failed" if is_retry else "completed",
                    model_id=sub_agent_model_id(result_tool_name),
                    summary=summary,
                    succeeded=not is_retry,
                )
            ),
        )
        ledger = derive_ledger(deps.state, deps.intent)
        _emit_chunk(writer, ledger_update_event(ledger=ledger))
