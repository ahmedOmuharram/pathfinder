from __future__ import annotations

from enum import StrEnum
from typing import Literal

from assistant_core.graph.turn_state import TurnState
from assistant_core.memory.schemas import MemoryEntryDraft
from assistant_core.platform.pydantic_base import CamelModel
from pydantic import BaseModel, ConfigDict, Field

from pathfinder.ai.agents.state import SearchOverview
from pathfinder.ai.lead.intent import UserIntent
from pathfinder.domain.strategy.build_outcome import (
    BuildOutcome,
)
from pathfinder.domain.strategy.operational_spec import OperationalSpec
from pathfinder.domain.strategy.staleness import StaleBuild

PhaseName = Literal[
    "frame",
    "build",
    "verification",
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
            "True if the strategy answered the user's question: sample "
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


class StrategyDomainState(BaseModel):
    """What the investigation knows: the framed spec, the searches it saw,
    the last build and its verification."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    user_intent: UserIntent | None = None
    lead_next_state: Literal["await_user", "complete"] | None = None
    operational_spec: OperationalSpec | None = None
    # The spec as the turn found it, written by the pre-turn hook. An edit's
    # dispositions are checked against this and never against the model's memory.
    spec_before_turn: OperationalSpec | None = None
    discovered_searches: dict[str, SearchOverview] = Field(default_factory=dict)
    verification_digest: VerificationDigest | None = None
    last_build_outcome: BuildOutcome | None = None
    # Recomputed at the start of every Lead turn by comparing the live
    # strategy against ``last_build_outcome``. Never persisted: an edit that
    # was stale last turn is not stale after the next build.
    stale_build: StaleBuild | None = None
    created_gene_set_ids: list[str] = Field(default_factory=list)
    # Studies already sent a full EDA filter sheet, with their vocabularies.
    sheeted_eda_datasets: set[str] = Field(default_factory=set)

    def mark_eda_sheet_shown(self, dataset_id: str) -> None:
        self.sheeted_eda_datasets.add(dataset_id)

    def was_eda_sheet_shown(self, dataset_id: str) -> bool:
        """Whether this study's vocabularies were already sent this turn.

        A second sheet repeats them at full size, so it is sent without them.
        """
        return dataset_id in self.sheeted_eda_datasets


class PipelineState(TurnState):
    domain: StrategyDomainState = Field(default_factory=StrategyDomainState)
