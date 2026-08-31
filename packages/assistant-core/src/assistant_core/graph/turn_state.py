"""The turn state any assistant carries: the user's message, the turn's
accounting, and the deferred call the turn parked for a user or a worker."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, JsonValue
from pydantic_ai.ui.vercel_ai.request_types import (
    TextUIPart,
    ToolApprovalResponded,
)

from assistant_core.memory.schemas import MemoryValue
from assistant_core.platform.pydantic_base import CamelModel


class SubAgentApprovalCall(CamelModel):
    """One approval-required tool call a sub-agent stopped at."""

    tool_call_id: str
    tool_name: str
    args: dict[str, JsonValue] = Field(default_factory=dict)


class SubAgentApprovalPending(CamelModel):
    """A sub-agent run suspended on approvals, with the history that resumes it."""

    role: str
    approvals: list[SubAgentApprovalCall] = Field(default_factory=list)
    messages_json: str = ""


class ParkedCall(CamelModel):
    """One deferred tool call a turn parked, with the history that resumes it.

    A parked call is answered by the user, when it needs an approval, or by
    the worker, when it is a durable task.
    """

    phase: str
    tool_call_id: str
    tool_name: str
    tool_args: dict[str, JsonValue] = Field(default_factory=dict)
    prior_messages_json: str = ""
    # Set when the parked call belongs to a tool inside a sub-agent. The ids
    # above then name the dispatch call, not the tool that was parked.
    sub_agent: SubAgentApprovalPending | None = None


class PendingApproval(ParkedCall):
    # The user message this approval was raised under. Answering the card
    # leaves it unchanged, so a later turn with a different id carries a typed
    # reply rather than an answer.
    user_message_id: UUID | None = None


class PendingDurableCall(ParkedCall):
    """A tool call handed to a worker. Its task's result answers it."""

    task_id: UUID
    # The name the durable tool registered under, which is not always the name
    # the model called it by.
    durable_tool_name: str


class DurableDeferral(CamelModel):
    """What a durable tool recorded on the deps when it deferred its work."""

    task_id: UUID
    tool_name: str
    # Set when the durable call ran inside a sub-agent, so the completion turn
    # re-enters that run rather than the dispatch that started it.
    sub_agent: SubAgentApprovalPending | None = None


class DurableTaskResult(CamelModel):
    """The worker's answer to one durable call."""

    task_id: UUID
    status: Literal["success", "failed"]
    result: dict[str, JsonValue] = Field(default_factory=dict)
    error: str = ""

    def as_tool_value(self) -> dict[str, JsonValue]:
        """The value the tool would have returned."""
        if self.status == "failed":
            return {"status": "failed", "error": self.error}
        return {"status": "success", "result": dict(self.result)}


ConsultQuestionKind = Literal["single_choice", "multi_choice", "free_text"]


class ConsultOption(CamelModel):
    """One selectable option on a ``consult_user`` question."""

    label: str
    description: str = ""
    recommended: bool = False


class ConsultQuestion(CamelModel):
    """A design question the assistant asks the user via ``consult_user`` to
    shape the work BEFORE a plan is finalized. Rendered as a carousel slide
    with options + an optional free-text note."""

    id: str
    prompt: str
    kind: ConsultQuestionKind = "single_choice"
    options: list[ConsultOption] = Field(default_factory=list)
    context: str = ""
    allow_notes: bool = True


class UserQuestionAnswer(CamelModel):
    """The user's answer to one ``ConsultQuestion``: chosen option label(s)
    and/or a free-text note. ``chosen_labels`` is empty for free_text."""

    # It is a tool return value, and a tool return reaches the wire through a
    # serializer that names no aliases, so the model names them itself.
    model_config = ConfigDict(serialize_by_alias=True)

    question_id: str
    prompt: str
    chosen_labels: list[str] = Field(default_factory=list)
    note: str = ""


class TurnState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    conversation_id: UUID
    user_id: UUID
    site_id: str
    mode: str

    user_message_id: UUID | None = None
    user_prompt: str = ""
    user_parts: list[TextUIPart] = Field(default_factory=list)
    turn_trace_id: str | None = None
    turn_created_at: str | None = None
    turn_message_id: UUID = Field(default_factory=uuid4)
    turn_start_event_id: int = 0

    turn_total_tokens: int = 0
    turn_total_cost_usd: Decimal = Field(default_factory=lambda: Decimal(0))

    # The thread's own messages, as the last settled turn left them. Serialized
    # with ``ModelMessagesTypeAdapter``; the graph that runs one agent reads it
    # as the run's history.
    thread_messages_json: str = ""

    pending_approval: PendingApproval | None = None
    pending_durable_call: PendingDurableCall | None = None
    # Set only on the turn the worker starts to answer a durable call.
    durable_result: DurableTaskResult | None = None
    approval_responses: dict[str, ToolApprovalResponded] = Field(
        default_factory=dict,
    )
    user_question_answers: dict[str, list[UserQuestionAnswer]] = Field(
        default_factory=dict,
    )
    retrieved_memories: list[MemoryValue] = Field(default_factory=list)

    @property
    def answered_durable_call(self) -> PendingDurableCall | None:
        """The parked durable call this turn carries the worker's answer for."""
        parked = self.pending_durable_call
        result = self.durable_result
        if parked is None or result is None or result.task_id != parked.task_id:
            return None
        return parked

    @property
    def resumes_parked_call(self) -> bool:
        """Whether this turn re-enters a run the thread parked."""
        return (
            self.pending_approval is not None or self.answered_durable_call is not None
        )
