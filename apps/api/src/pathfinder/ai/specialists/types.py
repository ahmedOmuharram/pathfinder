from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Discriminator, Field

from pathfinder.ai.memory.schemas import MemoryValue
from pathfinder.platform.pydantic_base import CamelModel

SpecialistKind = Literal["validate", "research"]


StepKind = Literal["search", "combine", "transform"]


class StepSummary(CamelModel):
    step_id: int | None = None
    local_step_id: str
    kind: StepKind
    display_name: str
    search_name: str
    record_class_name: str
    estimated_size: int | None = None


class ControlTestRun(CamelModel):
    task_id: UUID
    step_id: int
    status: Literal["succeeded", "failed", "running", "cancelled"]
    summary: str = ""
    completed_at: datetime | None = None


class BiologicalFocus(CamelModel):
    organism: str | None = None
    gene_family: str | None = None
    pathway: str | None = None
    other: str | None = None


class TurnExcerpt(CamelModel):
    role: Literal["user", "assistant"]
    text: str = Field(default="", max_length=2000)
    tool_call_count: int = 0
    created_at: datetime


class ValidateContext(CamelModel):
    kind: Literal["validate"] = "validate"
    strategy_name: str
    steps: list[StepSummary] = Field(default_factory=list)
    focused_step_id: int | None = None
    user_success_criteria: str = ""
    prior_control_test_runs: list[ControlTestRun] = Field(default_factory=list)
    relevant_memories: list[MemoryValue] = Field(default_factory=list)
    recent_turns: list[TurnExcerpt] = Field(default_factory=list, max_length=5)


class ResearchContext(CamelModel):
    kind: Literal["research"] = "research"
    research_question: str = ""
    current_strategy_summary: str = ""
    biological_focus: BiologicalFocus | None = None
    relevant_memories: list[MemoryValue] = Field(default_factory=list)
    recent_turns: list[TurnExcerpt] = Field(default_factory=list, max_length=5)


SpecialistContext = Annotated[
    ValidateContext | ResearchContext, Discriminator("kind"),
]


class SpecialistMode(CamelModel):
    kind: SpecialistKind
    entered_at: datetime
    model_id: str
    context: SpecialistContext
