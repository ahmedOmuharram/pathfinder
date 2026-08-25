"""Catalog inspection tools: search overview and parameter vocabularies.

Tools that take an opaque identifier (search name, parameter id) raise
``ModelRetry`` with did-you-mean candidates so the model corrects itself in
the same step.
"""

from typing import Any, Literal

from assistant_core.platform.pydantic_base import CamelModel
from pydantic_ai import RunContext
from pydantic_ai.exceptions import ModelRetry

from pathfinder.ai.agents.state import ParamVocabSnapshot
from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.tools.standalone._catalog_models import register_search
from pathfinder.domain.parameters.values import coerce_context_values
from pathfinder.services.catalog.overview_formatting import SearchOverviewResult
from pathfinder.services.catalog.param_formatting import (
    GetParameterOptionsResult,
    ParameterInfo,
)
from pathfinder.services.catalog.search_inspection import (
    UnknownSearchError,
    inspect_search,
    read_parameter_options,
)


class AlreadyReadNotice(CamelModel):
    """Returned when the model re-reads something it already read this turn.

    The full payload is suppressed because the model already holds it.
    """

    kind: Literal["already_read"] = "already_read"
    message: str
    search_name: str
    parameter_id: str | None = None


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
    try:
        inspection = await inspect_search(
            deps.site_id,
            search_name,
            record_type=record_type,
            query=deps.agent_state.operational_spec_draft.goal,
        )
    except UnknownSearchError as exc:
        raise ModelRetry(exc.guidance) from exc

    register_search(deps.agent_state, inspection.definition, inspection.record_type)

    return inspection.overview


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
    result = await read_parameter_options(
        deps.site_id,
        search_name,
        parameter_id,
        record_type=record_type,
        context_values=typed_context,
        query=query,
    )
    if result.kind == "parameter_info":
        _snapshot_param_vocab(deps, search_name, result)
        deps.agent_state.mark_param_read(read_key)
    return result


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
