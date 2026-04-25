"""Standalone catalog v2 tools for pydantic-ai migration.

Three focused tools replacing the old get_search_parameters / get_dependent_vocab:

1. ``get_search_overview`` -- high-level overview + state registration
2. ``get_parameter_options`` -- drill into one parameter's vocabulary
3. ``get_parameter_dependencies`` -- dependency DAG for fill ordering

Tools that take an opaque-identifier argument (search name, parameter id)
raise :class:`pydantic_ai.exceptions.ModelRetry` with did-you-mean
candidates instead of returning a tool error. The library threads the
retry message back into the same step so the model self-corrects on the
next request — no wasted round-trip, no spammed retry loop.
"""

from difflib import get_close_matches

from pydantic_ai import RunContext
from pydantic_ai.exceptions import ModelRetry

from pathfinder.ai.agents.state import SearchOverview, SearchSelectionStatus
from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.tools.standalone._catalog_models import (
    DependencyDag,
    _build_dependency_dag,
    _filter_vocab,
    _resolve_record_type,
)
from pathfinder.domain.strategy.types import DecodedParamsField
from pathfinder.services.catalog.overview_formatting import (
    SearchOverviewResult,
    format_search_overview,
)
from pathfinder.services.catalog.param_formatting import (
    ParameterInfo,
    format_typed_param,
)
from pathfinder.services.wdk import (
    WDKBaseParameter,
    WDKParameter,
    encode_wdk_params,
    get_wdk_client,
)


def _did_you_mean(
    candidate: str, valid: list[str], *, kind: str, search_name: str | None = None,
) -> str:
    """Build a ``ModelRetry`` message body that lists candidates the model
    can copy verbatim. Anthropic / OpenAI both treat this as the model's
    cue to re-emit the tool call with one of the listed values."""
    suggestions = get_close_matches(candidate, valid, n=5, cutoff=0.3)
    where = f" on search {search_name!r}" if search_name else ""
    parts = [f"{kind} {candidate!r} does not exist{where}."]
    if suggestions:
        parts.append(f"Did you mean: {suggestions}?")
    parts.append(f"Valid {kind} values: {sorted(valid)}.")
    return " ".join(parts)


def _fix_gene(record_type: str | None) -> str | None:
    """Rewrite 'gene' to None so _resolve_record_type auto-resolves.

    The 'gene' record type has almost no searches — models pick it by mistake
    when looking for gene searches, which actually live under 'transcript'.
    Passing None lets the SearchCatalog find the correct record type.
    """
    if record_type == "gene":
        return None
    return record_type


async def get_search_overview(
    ctx: RunContext[AgentDeps],
    search_name: str,
    record_type: str | None = None,
) -> SearchOverviewResult:
    """Get a high-level overview of a search: description, parameters (required/optional), and dependencies.

    MUST be called before creating a step with this search -- it registers the
    search in the discovery gate and caches the parameter schema.

    Args:
        ctx: Agent run context.
        search_name: WDK search name (urlSegment), e.g. 'GenesByText'.
        record_type: Record type. Auto-resolved from search name if omitted (recommended).
    """
    deps = ctx.deps
    rt = await _resolve_record_type(deps.site_id, search_name, _fix_gene(record_type))
    client = get_wdk_client(deps.site_id)
    details = await client.get_search_details(rt, search_name, expand_params=True)
    search = details.search_data
    params: list[WDKParameter] = search.parameters or []

    overview_result = format_search_overview(
        search_name=search.url_segment,
        display_name=search.display_name or search.url_segment,
        description=search.description or search.summary,
        record_type=rt,
        params=params,
    )

    # Register in agent state (discovery gate)
    visible_params = [
        p for p in params
        if p.is_visible
    ]
    overview = SearchOverview(
        search_name=search.url_segment,
        display_name=search.display_name or search.url_segment,
        record_type=rt,
        description=search.description or search.summary,
        parameter_names=[p.name for p in visible_params],
        required_params=[
            p.name for p in visible_params
            if not p.allow_empty_value or p.min_selected_count >= 1
        ],
    )
    deps.agent_state.register_search(search.url_segment, overview)

    return overview_result


async def get_parameter_options(
    ctx: RunContext[AgentDeps],
    search_name: str,
    parameter_id: str,
    record_type: str | None = None,
    context_values: DecodedParamsField | None = None,
    query: str | None = None,
) -> ParameterInfo:
    """Get detailed parameter info including vocabulary/allowed values.

    For dependent parameters, pass context_values with the parent parameter's
    chosen value to get the refreshed vocabulary.

    Args:
        ctx: Agent run context.
        search_name: WDK search name (urlSegment).
        parameter_id: Opaque WDK parameter identifier (e.g. ``min_pct_idents``).
            MUST be one of the names returned by ``get_search_overview`` for
            this search — copy verbatim, do not paraphrase.
        record_type: Record type. Auto-resolved from search name if omitted (recommended).
        context_values: Current parameter values (paramName -> value) for dependent vocab refresh.
        query: Optional substring filter for large vocabularies. Case-insensitive.
            Use when vocabulary is large and you need specific entries
            (e.g. query='cruzi' for T. cruzi).
    """
    deps = ctx.deps
    rt = await _resolve_record_type(deps.site_id, search_name, _fix_gene(record_type))
    has_context = bool(
        context_values
        and any(v is not None and v != "" for v in context_values.values())
    )

    client = get_wdk_client(deps.site_id)

    if has_context and context_values is not None:
        encoded_ctx = encode_wdk_params(dict(context_values))
        result = await client.get_search_details_with_params(
            rt, search_name, context=encoded_ctx, expand_params=True,
        )
        all_params = result.search_data.parameters or []
    else:
        details = await client.get_search_details(
            rt, search_name, expand_params=True,
        )
        all_params = details.search_data.parameters or []

    # Build dependency maps for annotation
    depends_on: dict[str, list[str]] = {}
    controls: dict[str, list[str]] = {}
    for p in all_params:
        base: WDKBaseParameter = p
        if base.dependent_params:
            controls[base.name] = list(base.dependent_params)
            for dep in base.dependent_params:
                depends_on.setdefault(dep, []).append(base.name)

    for p in all_params:
        if p.name == parameter_id:
            filtered = _filter_vocab(p, query) if query else p
            return format_typed_param(filtered, depends_on=depends_on, controls=controls)

    raise ModelRetry(
        _did_you_mean(
            parameter_id,
            [p.name for p in all_params],
            kind="parameter_id",
            search_name=search_name,
        ),
    )


async def update_search_decision(
    ctx: RunContext[AgentDeps],
    search_name: str,
    selection_status: SearchSelectionStatus,
    rationale: str,
    selection_reason: str = "",
    confidence: float = 0.0,
    param_hints: dict[str, str | list[str]] | None = None,
) -> str:
    """Commit discovery's decision about an already-inspected search.

    Call this AFTER ``get_search_overview`` (and any parameter inspection)
    to record what you concluded — biological rationale, whether you're
    keeping it, why, and any parameter values you already settled on.
    Downstream phases (planning, execution, verification) read this
    instead of replaying your tool history.

    Args:
        search_name: WDK search urlSegment that was previously inspected.
        selection_status: ``selected`` (committing this search to the plan),
            ``candidate`` (still considering), or ``rejected`` (ruling out
            but worth recording so planning doesn't re-discover it).
        rationale: Why this search is biologically relevant to the user's
            question. Reuse on every call — this is the "elevator pitch"
            for the search, not the decision justification.
        selection_reason: Short justification for the current
            ``selection_status`` decision (e.g. "primary anchor for kinase
            filter" or "user wants RNA-seq, not microarray").
        confidence: 0..1 confidence that this search fits.
        param_hints: Parameter values you settled on during inspection
            (raw WDK form). Planning will use these as starting defaults.
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
    updated = existing.model_copy(
        update={
            "selection_status": selection_status,
            "rationale": rationale,
            "selection_reason": selection_reason,
            "confidence": confidence,
            "param_hints": dict(param_hints) if param_hints else {},
        },
    )
    deps.agent_state.register_search(search_name, updated)
    return (
        f"Recorded {selection_status} decision for {search_name} "
        f"(confidence {confidence:.2f})."
    )


async def get_parameter_dependencies(
    ctx: RunContext[AgentDeps],
    search_name: str,
    record_type: str | None = None,
) -> DependencyDag:
    """Get the parameter dependency DAG for a search.

    Returns fillOrder (topologically sorted) and per-parameter dependency info.
    Use this to determine which parameters must be set before others.

    Args:
        ctx: Agent run context.
        search_name: WDK search name (urlSegment).
        record_type: Record type. Auto-resolved from search name if omitted (recommended).
    """
    deps = ctx.deps
    rt = await _resolve_record_type(deps.site_id, search_name, _fix_gene(record_type))
    client = get_wdk_client(deps.site_id)
    details = await client.get_search_details(rt, search_name, expand_params=True)
    params: list[WDKParameter] = details.search_data.parameters or []

    return _build_dependency_dag(params)
