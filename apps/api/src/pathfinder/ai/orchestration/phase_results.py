"""Typed handoff objects between pipeline phases.

Each phase produces a result that the next phase consumes via
``AgentDeps``.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dataclass_field
from typing import Literal

from pydantic import Field

from pathfinder.ai.agents.state import SearchOverview
from pathfinder.domain.strategy.plan import StrategyPlan
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.platform.types import JSONObject


class ClarificationQuestion(CamelModel):
    """A user-facing question needed to tighten the problem frame."""

    question: str
    context: str = ""
    field: str | None = None
    priority: Literal["blocking", "optional"] = "blocking"
    options: list[str] = Field(default_factory=list)


class ResearchNote(CamelModel):
    """A concise note from non-WDK exploration during scoping."""

    source: str
    finding: str
    url: str | None = None
    citation_id: str | None = None


class ProblemFrame(CamelModel):
    """Structured problem statement handed from scoping into discovery."""

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


type PhaseName = Literal["scoping", "discovery", "planning", "verification"]
type PhaseDecisionName = Literal[
    "ask_user",
    "continue_to_discovery",
    "continue_to_planning",
    "present_plan",
    "complete",
]


class PhaseDecision(CamelModel):
    """Structured record of how a phase chose to exit."""

    phase: PhaseName
    decision: PhaseDecisionName
    summary: str
    questions: list[ClarificationQuestion] = Field(default_factory=list)


@dataclass(frozen=True)
class ScopingResult:
    """Output of the scoping phase."""

    problem_frame: ProblemFrame | None = None
    decision: PhaseDecision | None = None


@dataclass(frozen=True)
class DiscoveryResult:
    """Output of the discovery phase.

    Passed to the planning agent via ``AgentDeps.discovery_result``.
    The planning agent also receives the discovery agent's ``new_messages()``
    as ``message_history`` for full conversational context.
    """

    discovered_searches: dict[str, SearchOverview] = dataclass_field(default_factory=dict)
    research_notes: str = ""
    intent_summary: str = ""
    decision: PhaseDecision | None = None


@dataclass(frozen=True)
class PlanningResult:
    """Output of the planning phase."""

    approved_plan: StrategyPlan | None = None
    questions_answered: list[str] = dataclass_field(default_factory=list)
    decision: PhaseDecision | None = None


@dataclass(frozen=True)
class ExecutionResult:
    """Output of the execution phase."""

    wdk_strategy_id: int | None = None
    step_results: dict[str, JSONObject] = dataclass_field(default_factory=dict)
    errors: list[str] = dataclass_field(default_factory=list)


@dataclass(frozen=True)
class VerificationResult:
    """Output of the verification phase."""

    assessment: str = ""
    sample_record_count: int = 0
    enrichment_ran: bool = False
    decision: PhaseDecision | None = None
