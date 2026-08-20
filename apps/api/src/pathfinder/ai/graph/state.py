from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, JsonValue
from pydantic_ai.ui.vercel_ai.request_types import (
    TextUIPart,
    ToolApprovalResponded,
)

from pathfinder.ai.agents.roles import PhaseRole
from pathfinder.ai.agents.state import SearchOverview
from pathfinder.ai.lead.intent import UserIntent
from pathfinder.ai.memory.schemas import MemoryEntryDraft, MemoryValue
from pathfinder.domain.strategy.build_outcome import BuildOutcome
from pathfinder.domain.strategy.operational_spec import OperationalSpec
from pathfinder.domain.strategy.staleness import StaleBuild
from pathfinder.platform.pydantic_base import CamelModel

PhaseName = Literal[
    "frame",
    "build",
    "verification",
]
PendingApprovalPhase = Literal[
    "frame",
    "build",
    "verification",
    "lead",
]

PHASE_NAMES: tuple[PhaseName, ...] = (
    "frame",
    "build",
    "verification",
)


class PhaseDisposition(StrEnum):
    AWAITING_USER = "awaiting_user"
    HANDOFF = "handoff"
    DONE = "done"


class FailureCause(StrEnum):
    """Typed cause of a phase's exit, surfaced to the LLM supervisor."""

    VOCAB_REJECTED = "vocab_rejected"
    AMBIGUOUS_INTENT = "ambiguous_intent"
    SEARCH_INVALID = "search_invalid"
    PARTIAL_BUILD = "partial_build"
    UNRESOLVED_SLOTS = "unresolved_slots"
    TRANSIENT_ERROR = "transient_error"


class ConstraintCheck(CamelModel):
    label: str
    requested: str
    realized: str
    honored: bool
    note: str = ""


class VerificationDigest(CamelModel):
    disposition: PhaseDisposition = Field(
        description=(
            "Control-flow signal: 'done' = investigation is complete; "
            "'awaiting_user' = the turn ends; 'handoff' = transition to "
            "the next sub-agent."
        ),
    )
    prose: str = Field(
        min_length=1,
        max_length=4000,
        description="User-facing assistant message shown in the chat thread.",
    )
    reason: str = Field(
        min_length=1,
        max_length=280,
        description="Short routing explanation shown on the orchestrator card.",
    )
    handoff_to: PhaseName | None = None
    failure_cause: FailureCause | None = Field(default=None)
    note_refs: list[str] = Field(default_factory=list, max_length=10)
    success: bool = Field(
        description=(
            "True if the strategy answered the user's question — sample "
            "records and result sizes look right, control tests passed."
        ),
    )
    key_findings: list[str] = Field(default_factory=list, max_length=10)
    caveats: list[str] = Field(default_factory=list, max_length=10)
    constraint_report: list[ConstraintCheck] = Field(
        default_factory=list, max_length=12
    )
    remember: list[MemoryEntryDraft] = Field(
        default_factory=list,
        max_length=5,
    )


class SubAgentApprovalCall(CamelModel):
    """One approval-required tool call a sub-agent stopped at."""

    tool_call_id: str
    tool_name: str
    args: dict[str, JsonValue] = Field(default_factory=dict)


class SubAgentApprovalPending(CamelModel):
    """A sub-agent run suspended on approvals, with the history that resumes it."""

    role: PhaseRole
    approvals: list[SubAgentApprovalCall] = Field(default_factory=list)
    messages_json: str = ""


class PendingApproval(CamelModel):
    phase: PendingApprovalPhase
    tool_call_id: str
    tool_name: str
    tool_args: dict[str, JsonValue] = Field(default_factory=dict)
    plan_id: str | None = None
    prior_messages_json: str = ""
    # Set when the approval belongs to a tool inside a sub-agent. The ids above
    # then name the Lead's dispatch call, not the tool the user answers.
    sub_agent: SubAgentApprovalPending | None = None
    # The user message this approval was raised under. Answering the card
    # leaves it unchanged, so a later turn with a different id carries a typed
    # reply rather than an answer.
    user_message_id: UUID | None = None


SUB_AGENT_APPROVAL_PHASE: dict[PhaseRole, PendingApprovalPhase] = {
    "frame": "frame",
    "execution": "build",
    "verification": "verification",
}


ConsultQuestionKind = Literal["single_choice", "multi_choice", "free_text"]


class ConsultOption(CamelModel):
    """One selectable option on a ``consult_user`` question."""

    label: str
    description: str = ""
    recommended: bool = False


class ConsultQuestion(CamelModel):
    """A design question the Lead asks the user via ``consult_user`` to shape
    the investigation BEFORE a plan is finalized. Rendered as a carousel slide
    with options + an optional free-text note."""

    id: str
    prompt: str
    kind: ConsultQuestionKind = "single_choice"
    options: list[ConsultOption] = Field(default_factory=list)
    context: str = ""
    allow_notes: bool = True


class UserQuestionAnswer(CamelModel):
    """The user's answer to one ``ConsultQuestion`` — chosen option label(s)
    and/or a free-text note. ``chosen_labels`` is empty for free_text."""

    question_id: str
    prompt: str
    chosen_labels: list[str] = Field(default_factory=list)
    note: str = ""


class PipelineState(BaseModel):
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

    user_intent: UserIntent | None = None
    lead_next_state: Literal["await_user", "complete"] | None = None
    operational_spec: OperationalSpec | None = None
    discovered_searches: dict[str, SearchOverview] = Field(default_factory=dict)
    verification_digest: VerificationDigest | None = None
    last_build_outcome: BuildOutcome | None = None
    # Recomputed at the start of every Lead turn by comparing the live
    # strategy against ``last_build_outcome``. Never persisted: an edit that
    # was stale last turn is not stale after the next build.
    stale_build: StaleBuild | None = None
    pending_approval: PendingApproval | None = None
    approval_responses: dict[str, ToolApprovalResponded] = Field(
        default_factory=dict,
    )
    user_question_answers: dict[str, list[UserQuestionAnswer]] = Field(
        default_factory=dict,
    )
    created_gene_set_ids: list[str] = Field(default_factory=list)
    retrieved_memories: list[MemoryValue] = Field(default_factory=list)
