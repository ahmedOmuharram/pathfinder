from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from pathfinder.ai.agents.state import SearchOverview
from pathfinder.ai.memory.schemas import MemoryEntryDraft, MemoryValue
from pathfinder.domain.strategy.plan import StrategyPlan
from pathfinder.platform.pydantic_base import CamelModel

PhaseName = Literal[
    "scoping",
    "discovery",
    "planning",
    "execution",
    "verification",
]

PHASE_NAMES: tuple[PhaseName, ...] = (
    "scoping",
    "discovery",
    "planning",
    "execution",
    "verification",
)


class PhaseDisposition(StrEnum):
    """How a phase agent wants the turn to proceed after it finishes."""

    AWAITING_USER = "awaiting_user"
    """Phase handed the turn back to the user — halt; don't run more phases."""

    HANDOFF = "handoff"
    """Phase is done; let the supervisor route to the next phase this turn."""

    DONE = "done"
    """Investigation complete — the whole turn should end after this phase."""


class PhaseOutcome(CamelModel):
    """A phase agent's structured final answer.

    Pydantic-ai's ``output_type=PhaseOutcome`` forces every phase to end the
    turn with an instance of this model — no free prose endings, no
    side-channel signalling tools.

    Three fields, three distinct audiences:

    * ``prose`` — the user-facing message (what the assistant "says"). The
      phase node emits this as a streamed text chunk so the chat UI renders
      it as a normal assistant reply.
    * ``reason`` — a short internal routing explanation shown on the
      orchestrator card and logged. Mirrors what the supervisor uses when
      short-circuiting.
    * ``disposition`` + ``handoff_to`` — the control-flow signal the
      supervisor reads to decide whether to halt, continue, or pick a
      specific next phase.
    """

    disposition: PhaseDisposition = Field(
        description=(
            "Control-flow signal for the supervisor. "
            "'awaiting_user' = the turn ends; the user must reply before any "
            "more phases run — use whenever the phase asked questions, made "
            "assumptions worth confirming, or surfaced ambiguity. Default "
            "for a first-turn scope. "
            "'handoff' = phase is done, supervisor routes to the next phase "
            "this turn — use only when everything was unambiguous and no "
            "user input is needed. "
            "'done' = investigation is complete; end the turn after this "
            "phase."
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
    note_refs: list[str] = Field(
        default_factory=list,
        max_length=10,
        description=(
            "Scratchpad note ids supporting this outcome. Optional; when "
            "populated, cites the notes that led to this conclusion."
        ),
    )


class VerificationDigest(PhaseOutcome):
    """Verification's structured close-out — extends ``PhaseOutcome``.

    Subclassing keeps the supervisor / orchestrator routing contract
    (disposition + prose + reason + handoff_to + note_refs) intact while
    layering on the verification-specific fields the autowrite path uses
    to make memory writes deterministic.
    """

    success: bool = Field(
        description=(
            "True if the strategy answered the user's question — sample "
            "records and result sizes look right, control tests passed. "
            "False if verification surfaced a real problem the next phase "
            "(or the user) needs to address."
        ),
    )
    key_findings: list[str] = Field(
        default_factory=list,
        max_length=10,
        description=(
            "Bullet-style facts the user should walk away with — counts, "
            "enrichments, surprising hits. One sentence each."
        ),
    )
    caveats: list[str] = Field(
        default_factory=list,
        max_length=10,
        description=(
            "Open issues, suspicious patterns, or limitations the user "
            "should know about even when ``success`` is True."
        ),
    )
    remember: list[MemoryEntryDraft] = Field(
        default_factory=list,
        max_length=5,
        description=(
            "Knowledge memories to autowrite — durable facts the user (or "
            "future agent runs) should recall next time. Use sparingly: "
            "only stable, reusable knowledge, not turn-specific results."
        ),
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
    blocking_questions: list[ClarificationQuestion] = Field(default_factory=list)
    optional_questions: list[ClarificationQuestion] = Field(default_factory=list)
    research_notes: list[ResearchNote] = Field(default_factory=list)
    ready_for_wdk_discovery: bool = False
    confidence: float = 0.0


class PendingApproval(CamelModel):
    """A deferred tool call awaiting user approval across turns.

    Written when a phase agent exits with a ``DeferredToolRequests`` output
    carrying an ``approvals`` entry. Carried through the LangGraph
    checkpoint so the next turn can resume the agent with a
    ``DeferredToolResults`` built from the user's reply.
    """

    phase: PhaseName
    tool_call_id: str
    tool_name: str
    tool_args: dict[str, JsonValue] = Field(default_factory=dict)
    plan_id: str | None = None


class PipelineState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    conversation_id: UUID
    user_id: UUID
    site_id: str
    mode: str

    user_message_id: UUID | None = None
    user_prompt: str = ""
    user_parts: list[dict[str, Any]] = Field(default_factory=list)
    turn_trace_id: str | None = None
    turn_created_at: str | None = None
    turn_message_id: UUID = Field(default_factory=uuid4)

    current_phase: PhaseName | None = None
    last_routing_reason: str | None = None
    supervisor_call_count: int = 0
    phase_call_counts: dict[PhaseName, int] = Field(default_factory=dict)
    last_assistant_prose: str = ""
    last_phase_outcome: PhaseOutcome | None = None
    last_verification_message_id: UUID | None = None

    turn_message_parts: list[dict[str, Any]] = Field(default_factory=list)

    turn_total_tokens: int = 0
    turn_total_cost_usd: Decimal = Field(default_factory=lambda: Decimal(0))

    problem_frame: ProblemFrame | None = None
    discovered_searches: dict[str, SearchOverview] = Field(default_factory=dict)
    active_plan: StrategyPlan | None = None
    verification_digest: VerificationDigest | None = None
    pending_approval: PendingApproval | None = None
    created_gene_set_ids: list[str] = Field(default_factory=list)
    retrieved_memories: list[MemoryValue] = Field(default_factory=list)
