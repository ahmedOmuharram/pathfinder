"""The deferred-tool cycle: parking a tool call the user must answer.

A run whose output is ``DeferredToolRequests`` stopped at an approval. The
turn parks it on the state, the wire carries the approval request, and the
next turn feeds the user's answer back into the same run.
"""

from __future__ import annotations

from pydantic_ai.messages import ModelMessage, ModelMessagesTypeAdapter, ToolCallPart
from pydantic_ai.tools import (
    DeferredToolApprovalResult,
    DeferredToolRequests,
    DeferredToolResults,
    ToolDenied,
)
from pydantic_ai.ui.vercel_ai.request_types import ToolApprovalResponded

from assistant_core.conversation.vercel_adapter import DeferredToolHint
from assistant_core.graph.turn_state import PendingApproval

DENIED_WITHOUT_REASON = "User denied the tool call."


def parked_call(
    *,
    call: ToolCallPart,
    phase: str,
    messages: list[ModelMessage],
) -> PendingApproval:
    """One deferred call, with the history that resumes it.

    ``messages`` is the FULL run history: a run whose first action is the
    deferred call has no leading request in ``new_messages()``, and pydantic-ai
    rejects an empty history on resume. An assistant that selects the call
    itself parks it here, then copies its own fields onto the result.
    """
    return PendingApproval(
        phase=phase,
        tool_call_id=call.tool_call_id,
        tool_name=call.tool_name,
        tool_args=call.args_as_dict(),
        prior_messages_json=ModelMessagesTypeAdapter.dump_json(messages).decode(),
    )


def pending_approval(
    *,
    output: DeferredToolRequests,
    phase: str,
    messages: list[ModelMessage],
) -> PendingApproval | None:
    """The approval a deferred run waits on, when the run raised one."""
    if not output.approvals:
        return None
    return parked_call(call=output.approvals[0], phase=phase, messages=messages)


def approval_answer(
    response: ToolApprovalResponded,
) -> bool | DeferredToolApprovalResult:
    """The user's click as the result the deferred call resumes with."""
    if response.approved:
        return True
    return ToolDenied(message=response.reason or DENIED_WITHOUT_REASON)


def approval_results(
    approval: PendingApproval,
    responses: dict[str, ToolApprovalResponded],
) -> DeferredToolResults | None:
    """The user's answer as the results the run resumes with, when answered."""
    response = responses.get(approval.tool_call_id)
    if response is None:
        return None
    return DeferredToolResults(
        approvals={approval.tool_call_id: approval_answer(response)},
    )


def resume_history(approval: PendingApproval) -> list[ModelMessage]:
    """The prior run's messages, so the model sees the call it asked about."""
    return ModelMessagesTypeAdapter.validate_json(approval.prior_messages_json)


def deferred_hint(approval: PendingApproval) -> DeferredToolHint:
    """What the resumed stream needs to re-announce the parked call."""
    return DeferredToolHint(
        tool_call_id=approval.tool_call_id,
        tool_name=approval.tool_name,
        tool_args=dict(approval.tool_args),
    )


__all__ = [
    "DENIED_WITHOUT_REASON",
    "approval_answer",
    "approval_results",
    "deferred_hint",
    "parked_call",
    "pending_approval",
    "resume_history",
]
