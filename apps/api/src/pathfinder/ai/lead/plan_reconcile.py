"""Deterministic reconciliation of an active plan against discovery's selected
searches.

When discovery commits a search with a ``replaces`` link (targeted
re-discovery after a denial), the plan leaf using the superseded search is
rewritten to the new search with parameters filled from the resolved vocab
snapshot — no LLM hand-editing. Topology (combines, connections, other leaves)
is left untouched. This makes denial→swap robust regardless of model.
"""

from __future__ import annotations

from pydantic import BaseModel

from pathfinder.ai.agents.state import ParamVocabSnapshot, SearchOverview
from pathfinder.domain.parameters.values import (
    ParamValue,
    as_param_kind,
    param_value_from_raw,
)
from pathfinder.domain.strategy.plan import (
    ParamStatus,
    PlannedParameter,
    PlannedStep,
    StepType,
    StrategyPlan,
)


class ReconcileResult(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    plan: StrategyPlan
    changes: list[str]


def reconcile_plan_with_replacements(
    plan: StrategyPlan,
    discovered: dict[str, SearchOverview],
    *,
    infer_replacements: bool = False,
    supersedes: str | None = None,
) -> ReconcileResult:
    """Rewrite any plan leaf whose search was superseded to the replacement.

    Replacement is established, in priority order, by: (1) an explicit
    ``replaces`` link on a selected search; (2) *supersedes* — the Lead's
    denial classification naming the plan search to replace, mapped to the
    single newly-selected search not yet in the plan; (3) when
    *infer_replacements* is set, a single orphaned leaf (search no longer
    selected) plus a single new selection, mapped 1:1.
    """
    replacements = {
        ov.replaces: ov
        for ov in discovered.values()
        if ov.selection_status == "selected" and ov.replaces
    }
    leaf_searches = {
        step.search_name for step in plan.steps if step.step_type is StepType.LEAF
    }
    if supersedes and supersedes in leaf_searches and supersedes not in replacements:
        candidate = _single_new_candidate(
            leaf_searches, discovered, explicit=replacements
        )
        if candidate is not None:
            replacements[supersedes] = candidate
    if infer_replacements:
        inferred = _infer_replacement(plan, discovered, explicit=replacements)
        if inferred is not None:
            old_name, new_ov = inferred
            replacements[old_name] = new_ov
    if not replacements:
        return ReconcileResult(plan=plan, changes=[])

    new_steps: list[PlannedStep] = []
    changes: list[str] = []
    for step in plan.steps:
        replacement = replacements.get(step.search_name)
        if step.step_type is StepType.LEAF and replacement is not None:
            new_steps.append(
                step.model_copy(
                    update={
                        "search_name": replacement.search_name,
                        "display_name": replacement.display_name
                        or replacement.search_name,
                        "record_type": replacement.record_type,
                        "parameters": _leaf_params(replacement),
                    },
                ),
            )
            changes.append(f"{step.search_name} → {replacement.search_name}")
        else:
            new_steps.append(step)

    if not changes:
        return ReconcileResult(plan=plan, changes=[])

    new_plan = plan.model_copy(
        update={"steps": new_steps, "version": plan.version + 1},
    )
    return ReconcileResult(plan=new_plan, changes=changes)


def _single_new_candidate(
    leaf_searches: set[str],
    discovered: dict[str, SearchOverview],
    *,
    explicit: dict[str, SearchOverview],
) -> SearchOverview | None:
    """The one selected search not yet in the plan and not already a
    replacement target — or None if there are zero or several."""
    candidates = sorted(
        name
        for name, ov in discovered.items()
        if ov.selection_status == "selected"
        and name not in leaf_searches
        and ov not in explicit.values()
    )
    if len(candidates) != 1:
        return None
    return discovered[candidates[0]]


def _infer_replacement(
    plan: StrategyPlan,
    discovered: dict[str, SearchOverview],
    *,
    explicit: dict[str, SearchOverview],
) -> tuple[str, SearchOverview] | None:
    """Map a single orphaned plan leaf (its search no longer selected) to a
    single newly-selected search not yet in the plan. Returns None if the
    mapping is absent or ambiguous (more than one candidate on either side)."""
    selected = {
        name for name, ov in discovered.items() if ov.selection_status == "selected"
    }
    leaf_searches = {
        step.search_name for step in plan.steps if step.step_type is StepType.LEAF
    }
    orphaned = sorted(
        name for name in leaf_searches if name not in selected and name not in explicit
    )
    if len(orphaned) != 1:
        return None
    candidate = _single_new_candidate(leaf_searches, discovered, explicit=explicit)
    if candidate is None:
        return None
    return orphaned[0], candidate


def _leaf_params(overview: SearchOverview) -> list[PlannedParameter]:
    """Build typed parameters for a swapped leaf from the resolved snapshot.

    A value comes from ``param_hints`` (what discovery settled on) or the
    snapshot's ``default_value``. Required params with no value become
    ``NEEDS_USER_INPUT`` slots rather than guesses.
    """
    names = set(overview.param_hints) | {
        name for name, snap in overview.param_vocab.items() if snap.required
    }
    params: list[PlannedParameter] = []
    for name in sorted(names):
        snap = overview.param_vocab.get(name)
        params.append(_build_param(name, overview.param_hints.get(name), snap))
    return params


def _build_param(
    name: str,
    hint: str | list[str] | None,
    snap: ParamVocabSnapshot | None,
) -> PlannedParameter:
    kind = (
        as_param_kind(snap.param_type) if snap is not None else as_param_kind("string")
    )
    raw: object | None = hint
    if raw is None and snap is not None:
        raw = snap.default_value
    value: ParamValue | None = None
    if raw is not None and raw != "":
        value = param_value_from_raw(raw, kind)
    required = bool(snap and snap.required)
    if value is not None:
        status = ParamStatus.SET
    elif required:
        status = ParamStatus.NEEDS_USER_INPUT
    else:
        status = ParamStatus.DEFAULT
    options = (
        [v.value for v in snap.allowed_values]
        if snap is not None and snap.allowed_values is not None
        else None
    )
    return PlannedParameter(
        name=name,
        display_name=name,
        param_type=kind,
        value=value,
        status=status,
        required=required,
        description=snap.help if snap is not None else None,
        options=options,
    )
