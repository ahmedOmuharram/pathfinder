"""Structured state for the PathFinder agent.

``AgentToolState`` lives on each agent instance and tracks which searches
have been discovered (the **discovery gate**) and the current strategy plan.
``SearchOverview`` is the cached schema snapshot returned by the discovery
tools and stored per-search inside the state.
"""

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

from pathfinder.domain.strategy.plan import StrategyPlan

SearchSelectionStatus = Literal["candidate", "selected", "rejected"]


class SearchOverview(BaseModel):
    """Cached overview of a discovered search's parameter schema.

    Discovery registers each inspected search with a ``selection_status``
    so downstream phases see *both* what's available and what discovery
    thinks of each candidate. The ``rationale`` / ``selection_reason``
    / ``param_hints`` fields carry forward what used to live only in the
    discovery agent's raw model trace, so planning and verification can
    reconstruct discovery's reasoning without replaying its history.
    """

    search_name: str
    display_name: str
    record_type: str
    description: str
    parameter_names: list[str]
    required_params: list[str]

    selection_status: SearchSelectionStatus = "candidate"
    """Discovery's commitment level: still being considered, picked for the
    plan, or explicitly ruled out (kept around so planning doesn't re-discover)."""

    rationale: str = ""
    """Why this search is on the table biologically — fills the gap that the
    discovery agent's narrative used to leave only in tool-call history."""

    selection_reason: str = ""
    """Short justification for the current ``selection_status`` decision."""

    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    """Discovery's 0..1 confidence that this search fits the user's need."""

    param_hints: dict[str, str] = Field(default_factory=dict)
    """Parameter values discovery surfaced as good defaults (raw WDK form)."""


@dataclass
class AgentToolState:
    """Structured state for the PathFinder agent.

    Provides the **per-search discovery gate** — the core enforcement
    mechanism that prevents the model from creating steps for searches
    it hasn't inspected.
    """

    discovered_searches: dict[str, SearchOverview] = field(default_factory=dict)
    active_plan: StrategyPlan | None = None
    plan_history: list[StrategyPlan] = field(default_factory=list)

    def register_search(self, name: str, overview: SearchOverview) -> None:
        """Register a search as discovered, caching its overview."""
        self.discovered_searches[name] = overview

    def is_search_discovered(self, name: str) -> bool:
        """Return whether a search has been discovered."""
        return name in self.discovered_searches

    def get_overview(self, name: str) -> SearchOverview | None:
        """Return the cached overview for a search, or ``None``."""
        return self.discovered_searches.get(name)

    def set_plan(self, plan: StrategyPlan) -> None:
        """Set a new active plan, archiving the previous one."""
        if self.active_plan is not None:
            self.plan_history.append(self.active_plan)
        self.active_plan = plan

    def clear(self) -> None:
        """Reset all state — discovered searches, active plan, history."""
        self.discovered_searches.clear()
        self.active_plan = None
        self.plan_history.clear()
