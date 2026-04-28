from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, JsonValue
from pydantic_ai.ui.vercel_ai.request_types import (
    DataUIPart,
    ReasoningUIPart,
    TextUIPart,
    ToolInputAvailablePart,
    ToolOutputAvailablePart,
    ToolOutputErrorPart,
)

from pathfinder.ai.agents.state import SearchOverview
from pathfinder.ai.memory.schemas import MemoryEntryDraft, MemoryValue
from pathfinder.ai.specialists.types import SpecialistMode
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
    AWAITING_USER = "awaiting_user"
    HANDOFF = "handoff"
    DONE = "done"


class PhaseOutcome(CamelModel):
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
    phase: PhaseName
    tool_call_id: str
    tool_name: str
    tool_args: dict[str, JsonValue] = Field(default_factory=dict)
    plan_id: str | None = None
    # Real prior agent-run messages (serialized via
    # ``ModelMessagesTypeAdapter``) — required on resume so the provider
    # sees the original tool call it issued. A synthesized stub satisfies
    # pydantic-ai's local check but OpenAI rejects unknown tool_call_ids.
    prior_messages_json: str = ""


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

    current_phase: PhaseName | None = None
    last_routing_reason: str | None = None
    supervisor_call_count: int = 0
    phase_call_counts: dict[PhaseName, int] = Field(default_factory=dict)
    last_assistant_prose: str = ""
    last_phase_outcome: PhaseOutcome | None = None
    last_verification_message_id: UUID | None = None

    turn_message_parts: list[
        TextUIPart | ReasoningUIPart | ToolInputAvailablePart
        | ToolOutputAvailablePart | ToolOutputErrorPart | DataUIPart
    ] = Field(default_factory=list)

    turn_total_tokens: int = 0
    turn_total_cost_usd: Decimal = Field(default_factory=lambda: Decimal(0))

    problem_frame: ProblemFrame | None = None
    discovered_searches: dict[str, SearchOverview] = Field(default_factory=dict)
    active_plan: StrategyPlan | None = None
    verification_digest: VerificationDigest | None = None
    pending_approval: PendingApproval | None = None
    created_gene_set_ids: list[str] = Field(default_factory=list)
    retrieved_memories: list[MemoryValue] = Field(default_factory=list)

    specialist_mode: SpecialistMode | None = None
