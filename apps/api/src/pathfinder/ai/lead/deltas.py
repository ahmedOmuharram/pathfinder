from __future__ import annotations

from typing import Literal

from pydantic import Field, JsonValue

from pathfinder.ai.graph.state import (
    ClarificationQuestion,
    ProblemFrame,
    VerificationDigest,
)
from pathfinder.domain.strategy.build_outcome import BuildOutcome
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
    """Discovery sub-agent output.

    Selections and rejections are NOT carried here — discovery commits them
    via ``update_search_decision`` into ``agent_state.discovered_searches``,
    which the Ledger reads directly. This delta is a lightweight summary so
    the model never re-types heavy ``SearchOverview`` objects in its final
    output (the old shape caused validation-retry spirals).
    """

    findings_summary: str = ""
    open_questions: list[str] = Field(default_factory=list)


class PlanDelta(CamelModel):
    """Planning sub-agent output.

    The plan itself is NOT carried here — the planner builds it via
    ``create_plan`` (→ ``agent_state.active_plan``), which the Ledger reads
    directly. Re-emitting the full ``StrategyPlan`` as output caused
    validation-retry failures (displayName required, parameters as object
    not array). This delta is a lightweight summary only.
    """

    summary: str = ""


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
