from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

from pathfinder.domain.strategy.plan import StrategyPlan
from pathfinder.services.catalog.vocab_rendering import VocabEntry

SearchSelectionStatus = Literal["candidate", "selected", "rejected"]


class ParamVocabSnapshot(BaseModel):
    """Frozen vocabulary view for a parameter, captured during discovery.

    Mirrors the vocabulary fields of ``ParameterInfo``: a flat list of
    enum entries (``allowed_values``) OR a rendered tree string
    (``allowed_values_tree``) for multi-pick-vocabulary params. Planning
    consults this snapshot to commit values verbatim — never invents
    values not in the snapshot.
    """

    param_type: str
    required: bool
    default_value: str | None = None
    allowed_values: list[VocabEntry] | None = None
    allowed_values_tree: str | None = None


class SearchOverview(BaseModel):
    search_name: str
    display_name: str
    record_type: str
    description: str
    parameter_names: list[str]
    required_params: list[str]

    selection_status: SearchSelectionStatus = "candidate"
    rationale: str = ""
    selection_reason: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    param_hints: dict[str, str | list[str]] = Field(default_factory=dict)
    param_vocab: dict[str, ParamVocabSnapshot] = Field(default_factory=dict)


@dataclass
class AgentToolState:
    discovered_searches: dict[str, SearchOverview] = field(default_factory=dict)
    active_plan: StrategyPlan | None = None
    plan_history: list[StrategyPlan] = field(default_factory=list)

    def register_search(self, name: str, overview: SearchOverview) -> None:
        self.discovered_searches[name] = overview

    def is_search_discovered(self, name: str) -> bool:
        return name in self.discovered_searches

    def get_overview(self, name: str) -> SearchOverview | None:
        return self.discovered_searches.get(name)

    def discovered_search_names(self) -> set[str]:
        return set(self.discovered_searches)

    def selected_search_names(self) -> set[str]:
        return {
            name
            for name, ov in self.discovered_searches.items()
            if ov.selection_status == "selected"
        }

    def all_param_keys(self) -> set[str]:
        keys: set[str] = set()
        for ov in self.discovered_searches.values():
            keys.update(ov.parameter_names)
        return keys

    def param_keys_for(self, search_name: str) -> set[str]:
        ov = self.discovered_searches.get(search_name)
        if ov is None:
            return set()
        return set(ov.parameter_names)

    def set_plan(self, plan: StrategyPlan) -> None:
        if self.active_plan is not None:
            self.plan_history.append(self.active_plan)
        self.active_plan = plan

    def clear(self) -> None:
        self.discovered_searches.clear()
        self.active_plan = None
        self.plan_history.clear()
