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

from pathfinder.ai.agents.state import SearchOverview
from pathfinder.ai.lead.intent import UserIntent
from pathfinder.ai.memory.schemas import MemoryEntryDraft, MemoryValue
from pathfinder.domain.strategy.build_outcome import BuildOutcome
from pathfinder.domain.strategy.plan import StrategyPlan
from pathfinder.platform.pydantic_base import CamelModel

PhaseName = Literal[
    "scoping",
    "discovery",
    "planning",
    "execution",
    "verification",
]
PendingApprovalPhase = Literal[
    "scoping",
    "discovery",
    "planning",
    "execution",
    "verification",
    "lead",
]

PHASE_NAMES: tuple[PhaseName, ...] = (
    "scoping",
    "discovery",
    "planning",
    "execution",
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
    remember: list[MemoryEntryDraft] = Field(
        default_factory=list,
        max_length=5,
    )


class ClarificationQuestion(CamelModel):
    question: str
    context: str = ""
    field: str | None = None
    priority: Literal["blocking", "optional"] = "blocking"
    options: list[str] = Field(default_factory=list)


class ResearchNote(CamelModel):
    source: str
    finding: str
    url: str | None = None
    citation_id: str | None = None


class StrategySketchNode(CamelModel):
    """A loose sketch of one node in the strategy result graph.

    NOT a formal step — no parameter values, no real ids, no validated
    search names. Scoping populates this as a "what the answer will
    look like" outline so the Lead can show the user the rough shape
    of the investigation before discovery starts. Discovery uses these
    labels as hints when picking searches; planning uses them as a
    structural template.

    Use ``id``s like ``"s1"``, ``"s2"`` and reference them in
    ``inputs`` for combine nodes.
    """

    id: str = Field(max_length=8)
    kind: Literal["leaf", "combine", "transform"]
    label: str = Field(max_length=80)
    description: str = Field(max_length=240)
    inputs: list[str] = Field(default_factory=list)
    operator: (
        Literal[
            "UNION",
            "INTERSECT",
            "MINUS",
            "RMINUS",
            "COLOCATE",
            "LONLY",
            "RONLY",
        ]
        | None
    ) = None


class ProblemFrame(CamelModel):
    user_goal: str
    interpreted_goal: str
    organism_scope: str | None = None
    record_type: str | None = None
    biological_entities: list[str] = Field(default_factory=list)
    inclusion_criteria: list[str] = Field(default_factory=list)
    exclusion_criteria: list[str] = Field(default_factory=list)
    likely_data_sources: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    strategy_sketch: list[StrategySketchNode] = Field(
        default_factory=list,
        max_length=12,
    )
    blocking_questions: list[ClarificationQuestion] = Field(default_factory=list)
    optional_questions: list[ClarificationQuestion] = Field(default_factory=list)
    research_notes: list[ResearchNote] = Field(default_factory=list)
    ready_for_wdk_discovery: bool = False
    confidence: float = 0.0


class PendingApproval(CamelModel):
    phase: PendingApprovalPhase
    tool_call_id: str
    tool_name: str
    tool_args: dict[str, JsonValue] = Field(default_factory=dict)
    plan_id: str | None = None
    prior_messages_json: str = ""


class PlanSlotAnswer(CamelModel):
    """One user-supplied answer to a plan's NEEDS_USER_INPUT slot."""

    step_id: str
    param_name: str
    value: JsonValue


class PipelineState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

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
    problem_frame: ProblemFrame | None = None
    discovered_searches: dict[str, SearchOverview] = Field(default_factory=dict)
    active_plan: StrategyPlan | None = None
    verification_digest: VerificationDigest | None = None
    last_build_outcome: BuildOutcome | None = None
    pending_approval: PendingApproval | None = None
    approval_responses: dict[str, ToolApprovalResponded] = Field(
        default_factory=dict,
    )
    plan_slot_answers: dict[str, list[PlanSlotAnswer]] = Field(
        default_factory=dict,
    )
    created_gene_set_ids: list[str] = Field(default_factory=list)
    retrieved_memories: list[MemoryValue] = Field(default_factory=list)
