"""Standalone catalog v2 tools for pydantic-ai migration.

Three focused tools replacing the old get_search_parameters / get_dependent_vocab:

1. ``get_search_overview`` -- high-level overview + state registration
2. ``get_parameter_options`` -- drill into one parameter's vocabulary
3. ``get_parameter_dependencies`` -- dependency DAG for fill ordering
"""

from pydantic_ai import RunContext

from pathfinder.ai.agents.state import SearchOverview
from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.tools.standalone._catalog_models import (
    DependencyDag,
    _build_dependency_dag,
    _filter_vocab,
    _resolve_record_type,
)
from pathfinder.domain.strategy.types import DecodedParams
from pathfinder.platform.tool_errors import ToolErrorPayload, tool_error
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
    param_name: str,
    record_type: str | None = None,
    context_values: DecodedParams | None = None,
    query: str | None = None,
) -> ParameterInfo | ToolErrorPayload:
    """Get detailed parameter info including vocabulary/allowed values.

    For dependent parameters, pass context_values with the parent parameter's
    chosen value to get the refreshed vocabulary.

    Args:
        ctx: Agent run context.
        search_name: WDK search name (urlSegment).
        param_name: Parameter name to inspect.
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
        if p.name == param_name:
            filtered = _filter_vocab(p, query) if query else p
            return format_typed_param(filtered, depends_on=depends_on, controls=controls)

    return tool_error("PARAM_NOT_FOUND", f"Parameter '{param_name}' not found in search '{search_name}'.")


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
