from __future__ import annotations

from typing import Literal

from pydantic import Field, JsonValue, computed_field

from pathfinder.ai.agents.state import SearchOverview
from pathfinder.ai.graph.state import (
    ClarificationQuestion,
    ProblemFrame,
    VerificationDigest,
)
from pathfinder.domain.strategy.build_outcome import BuildOutcome
from pathfinder.domain.strategy.plan import (
    ParamStatus,
    StrategyPlan,
)
from pathfinder.platform.pydantic_base import CamelModel


class OpenSlot(CamelModel):
    """An unresolved parameter slot on the active plan."""

    step_id: str
    param_name: str
    status: Literal["needs_user_input", "needs_discovery"]
    question: str = ""
    options: list[JsonValue] = Field(default_factory=list)


class FrameDelta(CamelModel):
    """Scoping sub-agent output. Replaces the old PhaseOutcome shape.

    The Lead synthesizes user-facing prose from this + the Ledger; the
    delta itself is structured.
    """

    frame: ProblemFrame
    blocking_questions: list[ClarificationQuestion] = Field(default_factory=list)
    research_findings: str = ""


class DiscoveryDelta(CamelModel):
    """Discovery sub-agent output."""

    new_selections: list[SearchOverview] = Field(default_factory=list)
    new_rejections: list[SearchOverview] = Field(default_factory=list)
    findings_summary: str = ""
    open_questions: list[str] = Field(default_factory=list)


class PlanDelta(CamelModel):
    """Planning sub-agent output."""

    plan: StrategyPlan
    new_open_slots: list[OpenSlot] = Field(default_factory=list)

    @computed_field
    def has_unresolved_slots(self) -> bool:
        for step in self.plan.steps:
            for p in step.parameters:
                if p.status in (
                    ParamStatus.NEEDS_USER_INPUT,
                    ParamStatus.NEEDS_DISCOVERY,
                ):
                    return True
        return False


class ExecuteDelta(CamelModel):
    """Declarative execution output. No LLM ran; this is the build result."""

    outcome: BuildOutcome


class RecoveryDelta(CamelModel):
    """Execution-recovery sub-agent output (only invoked when build fails)."""

    actions_taken: list[str] = Field(default_factory=list)
    final_outcome: BuildOutcome
    follow_up_needed: bool = False


class VerificationDelta(CamelModel):
    """Verification sub-agent output."""

    digest: VerificationDigest
