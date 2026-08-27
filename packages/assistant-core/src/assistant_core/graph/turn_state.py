"""The turn state any assistant carries: the user's message, the turn's
accounting, and the approval or consult question the turn is blocked on."""

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


class PendingApproval(CamelModel):
    phase: str
    tool_call_id: str
    tool_name: str
    tool_args: dict[str, JsonValue] = Field(default_factory=dict)
    prior_messages_json: str = ""
    # Set when the approval belongs to a tool inside a sub-agent. The ids above
    # then name the Lead's dispatch call, not the tool the user answers.
    sub_agent: SubAgentApprovalPending | None = None
    # The user message this approval was raised under. Answering the card
    # leaves it unchanged, so a later turn with a different id carries a typed
    # reply rather than an answer.
    user_message_id: UUID | None = None


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
    approval_responses: dict[str, ToolApprovalResponded] = Field(
        default_factory=dict,
    )
    user_question_answers: dict[str, list[UserQuestionAnswer]] = Field(
        default_factory=dict,
    )
    retrieved_memories: list[MemoryValue] = Field(default_factory=list)
