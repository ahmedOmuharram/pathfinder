from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai.messages import ModelMessage

from pathfinder.ai.agents.state import SearchOverview
from pathfinder.ai.graph.messages_reducer import append_messages_safely
from pathfinder.ai.memory.schemas import MemoryValue
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

    current_phase: PhaseName | None = None
    last_routing_reason: str | None = None
    supervisor_call_count: int = 0
    phase_call_counts: dict[PhaseName, int] = Field(default_factory=dict)
    last_assistant_prose: str = ""
    last_verification_message_id: UUID | None = None

    message_history: Annotated[list[ModelMessage], append_messages_safely] = Field(
        default_factory=list,
    )

    problem_frame: ProblemFrame | None = None
    discovered_searches: dict[str, SearchOverview] = Field(default_factory=dict)
    active_plan: StrategyPlan | None = None
    created_gene_set_ids: list[str] = Field(default_factory=list)
    retrieved_memories: list[MemoryValue] = Field(default_factory=list)
