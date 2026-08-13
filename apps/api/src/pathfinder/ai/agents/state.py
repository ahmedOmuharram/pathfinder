from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

from pathfinder.domain.parameters.values import ParamValue
from pathfinder.domain.parameters.wdk_vocab import VocabOption
from pathfinder.domain.strategy.operational_spec import (
    Criterion,
    DroppedCriterion,
    OperationalSpec,
    SpecStructure,
)

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
    help: str = ""
    default_value: str | None = None
    allowed_values: list[VocabOption] | None = None
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
    replaces: str | None = None
    decided: bool = False


@dataclass
class AgentToolState:
    discovered_searches: dict[str, SearchOverview] = field(default_factory=dict)
    catalog_search_names: set[str] = field(default_factory=set)
    read_param_options: set[str] = field(default_factory=set)
    operational_spec_draft: OperationalSpec = field(default_factory=OperationalSpec)

    def frame_set_criterion(self, criterion: Criterion) -> None:
        spec = self.operational_spec_draft
        spec.criteria = [c for c in spec.criteria if c.id != criterion.id]
        spec.criteria.append(criterion)

    def frame_set_structure(self, structure: SpecStructure) -> None:
        self.operational_spec_draft.structure = structure

    def frame_drop_criterion(self, criterion_id: str, reason: str) -> bool:
        """Remove a criterion from the draft (keyed by id, like
        ``frame_set_criterion``) and record it in ``dropped``. Returns False if
        no criterion has that id — so a dropped criterion's open params can no
        longer keep ``ready_to_build`` False. Returns True when one was removed."""
        spec = self.operational_spec_draft
        match = next((c for c in spec.criteria if c.id == criterion_id), None)
        if match is None:
            return False
        spec.criteria = [c for c in spec.criteria if c.id != criterion_id]
        spec.dropped.append(DroppedCriterion(text=match.text, reason=reason))
        return True

    def resolved_params_for(self, search_name: str) -> dict[str, ParamValue]:
        """Params the draft spec has already bound on ``search_name``.

        A dependent vocabulary is only valid under its parent values, and WDK
        answers with the search defaults when no context is supplied.
        """
        if not search_name:
            return {}
        merged: dict[str, ParamValue] = {}
        for criterion in self.operational_spec_draft.criteria:
            if criterion.search_name == search_name:
                merged.update(criterion.resolved_params)
        return merged

    @staticmethod
    def param_read_key(
        search_name: str,
        parameter_id: str,
        *,
        context_values: dict[str, ParamValue] | None = None,
        query: str | None = None,
    ) -> str:
        """Stable key for one parameter-options read. Context-sensitive so a
        dependent param re-read under a different parent value is a new read,
        not a dedup hit."""
        ctx = ""
        if context_values:
            ctx = ";".join(
                f"{k}={v.model_dump_json()}" for k, v in sorted(context_values.items())
            )
        return f"{search_name}|{parameter_id}|{ctx}|{query or ''}"

    def mark_param_read(self, key: str) -> None:
        self.read_param_options.add(key)

    def was_param_read(self, key: str) -> bool:
        return key in self.read_param_options

    def decided_search_names(self) -> set[str]:
        return {n for n, ov in self.discovered_searches.items() if ov.decided}

    def register_search(self, name: str, overview: SearchOverview) -> None:
        self.discovered_searches[name] = overview

    def is_search_discovered(self, name: str) -> bool:
        return name in self.discovered_searches

    def get_overview(self, name: str) -> SearchOverview | None:
        return self.discovered_searches.get(name)

    def discovered_search_names(self) -> set[str]:
        return set(self.discovered_searches)

    def record_catalog_searches(self, names: list[str]) -> None:
        """Record search names returned by the catalog (search_for_searches /
        list_searches) so ``get_search_overview`` can be constrained to names
        the model has actually seen — never invented ones."""
        self.catalog_search_names.update(n for n in names if n)

    def candidate_search_names(self) -> set[str]:
        """Inspectable searches: catalog results plus already-inspected ones
        (re-inspection must not be masked)."""
        return self.catalog_search_names | set(self.discovered_searches)

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

    def clear(self) -> None:
        self.discovered_searches.clear()
        self.catalog_search_names.clear()
