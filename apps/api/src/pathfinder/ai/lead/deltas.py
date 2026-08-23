from __future__ import annotations

from typing import Literal

from assistant_core.platform.pydantic_base import CamelModel
from pydantic import Field

from pathfinder.ai.graph.state import VerificationDigest
from pathfinder.domain.strategy.build_outcome import BuildOutcome


class FrameResult(CamelModel):
    """FRAME sub-agent output. The OperationalSpec is committed to agent_state
    via tools (not re-typed here); this delta is a light summary + disposition."""

    summary: str = ""
    disposition: Literal["spec_ready", "needs_user", "needs_research"] = "spec_ready"
    open_questions: list[str] = Field(default_factory=list)


class ExecuteDelta(CamelModel):
    """Declarative BUILD output. No LLM ran; this is the build result."""

    outcome: BuildOutcome


class RecoveryDelta(CamelModel):
    """Execution-recovery sub-agent output (only invoked when build fails).

    The agent emits only the light fields; the resulting ``BuildOutcome`` is
    re-derived by re-syncing the strategy (the agent re-typing the full outcome
    object fumbled ``counts`` and caused a think-loop)."""

    actions_taken: list[str] = Field(default_factory=list)
    follow_up_needed: bool = False


class VerificationDelta(CamelModel):
    """Verification sub-agent output."""

    digest: VerificationDigest
