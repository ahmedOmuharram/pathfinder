"""Discovery decision tool: commit a verdict on an inspected search.

Split from ``catalog_discovery`` (which handles read-only catalog inspection)
to keep each module under the line cap. ``update_search_decision`` records the
selection verdict, enforces the resolve-before-select guard, and applies a
``replaces`` link (auto-rejecting the superseded search) for targeted swaps.
"""

from pydantic_ai import RunContext
from pydantic_ai.exceptions import ModelRetry

from pathfinder.ai.agents.state import SearchSelectionStatus
from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.tools.standalone.catalog_discovery import _did_you_mean


def _validate_and_reject_replaced(
    deps: AgentDeps,
    search_name: str,
    replaces: str,
) -> None:
    """Validate a ``replaces`` link and auto-reject the superseded search."""
    if replaces == search_name:
        msg = (
            f"replaces={replaces!r} cannot equal the search being selected. "
            "Set replaces to the OTHER search this one supersedes."
        )
        raise ModelRetry(msg)
    old = deps.agent_state.get_overview(replaces)
    if old is None:
        discovered = sorted(deps.agent_state.discovered_searches)
        msg = _did_you_mean(replaces, discovered, kind="search_name")
        raise ModelRetry(msg)
    rejected = old.model_copy(
        update={
            "selection_status": "rejected",
            "selection_reason": f"superseded by {search_name}",
            "decided": True,
        },
    )
    deps.agent_state.register_search(replaces, rejected)


async def update_search_decision(
    ctx: RunContext[AgentDeps],
    search_name: str,
    selection_status: SearchSelectionStatus,
    rationale: str,
    selection_reason: str = "",
    confidence: float = 0.0,
    param_hints: dict[str, str | list[str]] | None = None,
    replaces: str | None = None,
) -> str:
    """Commit discovery's decision about an already-inspected search.

    Call this AFTER ``get_search_overview`` (and any parameter inspection)
    to record what you concluded - biological rationale, whether you're
    keeping it, why, and any parameter values you already settled on.
    Downstream phases (planning, execution, verification) read this
    instead of replaying your tool history.

    Args:
        search_name: WDK search urlSegment that was previously inspected.
        selection_status: ``selected`` (committing this search to the plan),
            ``candidate`` (still considering), or ``rejected`` (ruling out
            but worth recording so planning doesn't re-discover it).
        rationale: Why this search is biologically relevant to the user's
            question. Reuse on every call - this is the "elevator pitch"
            for the search, not the decision justification.
        selection_reason: Short justification for the current
            ``selection_status`` decision (e.g. "primary anchor for kinase
            filter" or "user wants RNA-seq, not microarray").
        confidence: 0..1 confidence that this search fits.
        param_hints: Parameter values you settled on during inspection
            (raw WDK form). Planning will use these as starting defaults.
        replaces: When this selection SUPERSEDES a search already in the plan
            (a targeted re-discovery swap), pass that search's name here. The
            old search is auto-rejected and the plan leaf using it is rewritten
            to this search automatically - do NOT hand-edit the plan.
    """
    if not 0.0 <= confidence <= 1.0:
        msg = (
            f"confidence must be in [0, 1]; got {confidence}. "
            "Pick a value between 0.0 (no confidence this search fits) "
            "and 1.0 (certain it fits)."
        )
        raise ModelRetry(msg)
    deps = ctx.deps
    existing = deps.agent_state.get_overview(search_name)
    if existing is None:
        discovered = sorted(deps.agent_state.discovered_searches)
        if not discovered:
            msg = (
                f"Search {search_name!r} has not been inspected yet, and "
                "no searches have been inspected this turn. Call "
                "`get_search_overview` first to inspect a search."
            )
            raise ModelRetry(msg)
        raise ModelRetry(
            _did_you_mean(search_name, discovered, kind="search_name"),
        )
    if existing.decided and existing.selection_status == selection_status:
        return (
            f"Already decided '{search_name}' as {selection_status} - no change "
            "recorded. It's hidden from the catalog now; move on to other "
            "searches or finish discovery."
        )
    if selection_status == "selected":
        unresolved = [
            p for p in existing.required_params if p not in existing.param_vocab
        ]
        if unresolved:
            msg = (
                f"Cannot select {search_name!r}: required parameters "
                f"{unresolved} have no resolved vocabulary, so planning would "
                f"have to guess their values. Call get_search_overview("
                f"search_name={search_name!r}) first, then select."
            )
            raise ModelRetry(msg)
    if replaces is not None:
        _validate_and_reject_replaced(deps, search_name, replaces)
    updated = existing.model_copy(
        update={
            "selection_status": selection_status,
            "rationale": rationale,
            "selection_reason": selection_reason,
            "confidence": confidence,
            "param_hints": dict(param_hints) if param_hints else {},
            "replaces": replaces,
            "decided": True,
        },
    )
    deps.agent_state.register_search(search_name, updated)
    return (
        f"Recorded {selection_status} decision for {search_name} "
        f"(confidence {confidence:.2f})."
    )
