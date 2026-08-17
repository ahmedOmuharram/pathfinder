"""Catalog inspection tools: search overview and parameter vocabularies.

Tools that take an opaque identifier (search name, parameter id) raise
``ModelRetry`` with did-you-mean candidates so the model corrects itself in
the same step.
"""

from difflib import get_close_matches
from typing import Any, Literal

from pydantic_ai import RunContext
from pydantic_ai.exceptions import ModelRetry

from pathfinder.ai.agents.state import ParamVocabSnapshot
from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.tools.standalone._catalog_models import (
    _filter_vocab,
    _resolve_record_type,
    read_search_definition,
    register_search,
)
from pathfinder.domain.parameters.values import ParamValue, coerce_context_values
from pathfinder.platform.errors import WDKError
from pathfinder.platform.pydantic_base import CamelModel
from pathfinder.services.catalog.overview_formatting import (
    SearchOverviewResult,
    format_search_overview,
)
from pathfinder.services.catalog.param_formatting import (
    GetParameterOptionsResult,
    ParameterInfo,
    ParameterNotOnSearch,
    ParentContextRequired,
    format_param_info_typed,
    format_typed_param,
    phyletic_options_for,
)
from pathfinder.services.catalog.search_context import (
    get_search_params_under_context,
)
from pathfinder.services.catalog.searches import get_raw_searches
from pathfinder.services.wdk import (
    WDKBaseParameter,
    WDKParameter,
    encode_wdk_params,
    get_wdk_client,
)


class AlreadyReadNotice(CamelModel):
    """Returned when the model re-reads something it already read this turn.

    The full payload is suppressed because the model already holds it.
    """

    kind: Literal["already_read"] = "already_read"
    message: str
    search_name: str
    parameter_id: str | None = None


_SEARCH_NOT_FOUND_STATUS = 404


def _did_you_mean(
    candidate: str,
    valid: list[str],
    *,
    kind: str,
    search_name: str | None = None,
) -> str:
    """Build a retry message that lists valid candidates to copy verbatim."""
    suggestions = get_close_matches(candidate, valid, n=5, cutoff=0.3)
    where = f" on search {search_name!r}" if search_name else ""
    parts = [f"{kind} {candidate!r} does not exist{where}."]
    if suggestions:
        parts.append(f"Did you mean: {suggestions}?")
    parts.append(f"Valid {kind} values: {sorted(valid)}.")
    return " ".join(parts)


def _fix_gene(record_type: str | None) -> str | None:
    """Drop the 'gene' record type so the record type is auto-resolved.

    In WDK, gene searches live under the 'transcript' record type.
    """
    if record_type == "gene":
        return None
    return record_type


async def get_search_overview(
    ctx: RunContext[AgentDeps],
    search_name: str,
    record_type: str | None = None,
) -> SearchOverviewResult | AlreadyReadNotice:
    """Get a high-level overview of a search: description, parameters (required/optional), and dependencies.

    MUST be called before creating a step with this search -- it registers the
    search in the discovery gate and caches the parameter schema. Reading the
    same search twice returns a short "already inspected" notice, not a re-dump.

    Args:
        ctx: Agent run context.
        search_name: WDK search name (urlSegment), e.g. 'GenesByText'.
        record_type: Record type. Auto-resolved from search name if omitted (recommended).
    """
    deps = ctx.deps
    if deps.agent_state.get_overview(search_name) is not None:
        return AlreadyReadNotice(
            message=(
                f"You already inspected '{search_name}' this turn; same as "
                "your earlier read. Move on (inspect a different search, read a "
                "parameter, or record a decision)."
            ),
            search_name=search_name,
        )
    rt = await _resolve_record_type(deps.site_id, search_name, _fix_gene(record_type))
    try:
        search = await read_search_definition(deps.site_id, rt, search_name)
    except WDKError as exc:
        if exc.status != _SEARCH_NOT_FOUND_STATUS:
            raise
        valid = [
            s.url_segment
            for s in await get_raw_searches(deps.site_id, rt)
            if s.url_segment
        ]
        raise ModelRetry(_did_you_mean(search_name, valid, kind="search")) from exc
    params: list[WDKParameter] = search.parameters or []

    overview_result = format_search_overview(
        search_name=search.url_segment,
        display_name=search.display_name or search.url_segment,
        description=search.description or search.summary,
        record_type=rt,
        infos=format_param_info_typed(params),
        query=deps.agent_state.operational_spec_draft.goal,
    )

    register_search(deps.agent_state, search, rt)

    return overview_result


def _unbound_parents(
    all_params: list[WDKParameter],
    parameter_id: str,
    bound: dict[str, ParamValue] | None,
) -> list[str]:
    """The parents of `parameter_id` that carry no value yet.

    A dependent vocabulary is generated under its parents, so a read without
    them answers about the search's default parent rather than the one meant.
    """
    have = set(bound or {})
    return sorted(
        p.name
        for p in all_params
        if parameter_id in (p.dependent_params or []) and p.name not in have
    )


async def get_parameter_options(
    ctx: RunContext[AgentDeps],
    search_name: str,
    parameter_id: str,
    record_type: str | None = None,
    context_values: dict[str, Any] | None = None,
    query: str | None = None,
) -> GetParameterOptionsResult | AlreadyReadNotice:
    """Get detailed parameter info including vocabulary/allowed values.

    For dependent parameters, pass context_values with the parent parameter's
    chosen value to get the refreshed vocabulary.

    Returns a discriminated union:
      - ``ParameterInfo`` (``kind="parameter_info"``) on success.
      - ``ParameterNotOnSearch`` (``kind="parameter_not_on_search"``) when
        ``parameter_id`` does not exist on ``search_name``. The payload
        carries did-you-mean suggestions plus the full valid list; call
        again with one of them.

    Args:
        ctx: Agent run context.
        search_name: WDK search name (urlSegment).
        parameter_id: Opaque WDK parameter identifier (e.g. ``min_pct_idents``).
            MUST be one of the names returned by ``get_search_overview`` for
            this search; copy verbatim, do not paraphrase.
        record_type: Record type. Auto-resolved from search name if omitted (recommended).
        context_values: Current values of the parent parameters this param
            depends on, for dependent vocab refresh. Pass the RAW value: a
            string for a single pick, a list for multi-pick; the system types
            it. Example: ``{"profileset_generic": "<term>"}``.
        query: Optional substring filter for large vocabularies. Case-insensitive.
            Use when vocabulary is large and you need specific entries
            (e.g. query='cruzi' for T. cruzi).
    """
    deps = ctx.deps
    explicit = coerce_context_values(context_values) if context_values else {}
    # Parents already bound by the spec outrank WDK defaults; an explicit
    # argument outranks both.
    inherited = deps.agent_state.resolved_params_for(search_name)
    merged = {**inherited, **explicit}
    typed_context = merged or None
    read_key = deps.agent_state.param_read_key(
        search_name, parameter_id, context_values=typed_context, query=query
    )
    if deps.agent_state.was_param_read(read_key):
        return AlreadyReadNotice(
            message=(
                f"You already read options for '{parameter_id}' on "
                f"'{search_name}' with these exact context/query; same as "
                "before. Use the values you saw; don't re-read."
            ),
            search_name=search_name,
            parameter_id=parameter_id,
        )
    rt = await _resolve_record_type(deps.site_id, search_name, _fix_gene(record_type))
    result = await get_search_params_under_context(
        get_wdk_client(deps.site_id),
        rt,
        search_name,
        encode_wdk_params(dict(typed_context)) if typed_context else {},
    )
    all_params = result.search_data.parameters or []

    unbound = _unbound_parents(all_params, parameter_id, typed_context)
    if unbound:
        return ParentContextRequired(
            search_name=search_name,
            parameter_id=parameter_id,
            parent_parameter_ids=unbound,
            message=(
                f"'{parameter_id}' has a different vocabulary under each value of "
                f"{', '.join(unbound)}, so there is no list to show until one is "
                f"chosen. Read {unbound[0]} first, then call this again passing "
                f"context_values={{'{unbound[0]}': '<the value you chose>'}}."
            ),
        )

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
            info = format_typed_param(
                filtered,
                depends_on=depends_on,
                controls=controls,
                applied_context=typed_context,
                parent_defaults={
                    other.name: other.initial_display_value
                    for other in all_params
                    if other.initial_display_value
                },
                phyletic_options=phyletic_options_for(all_params, parameter_id, query),
            )
            _snapshot_param_vocab(deps, search_name, info)
            deps.agent_state.mark_param_read(read_key)
            return info

    valid = [p.name for p in all_params]
    suggestions = get_close_matches(parameter_id, valid, n=5, cutoff=0.3)
    return ParameterNotOnSearch(
        search_name=search_name,
        requested_parameter_id=parameter_id,
        message=_did_you_mean(
            parameter_id,
            valid,
            kind="parameter_id",
            search_name=search_name,
        ),
        suggestions=suggestions,
        valid_parameter_ids=sorted(valid),
    )


def _snapshot_param_vocab(
    deps: AgentDeps,
    search_name: str,
    info: ParameterInfo,
) -> None:
    overview = deps.agent_state.get_overview(search_name)
    if overview is None:
        return
    snapshot = ParamVocabSnapshot(
        param_type=info.type,
        required=info.required,
        help=info.help,
        default_value=info.default_value,
        allowed_values=info.allowed_values,
        allowed_values_tree=info.allowed_values_tree,
    )
    updated_vocab = {**overview.param_vocab, info.name: snapshot}
    updated = overview.model_copy(update={"param_vocab": updated_vocab})
    deps.agent_state.register_search(search_name, updated)
