"""Discovery-phase toolset — tools for exploring searches, literature, and catalogs."""

from pydantic_ai.tools import RunContext
from pydantic_ai.toolsets.abstract import AbstractToolset
from pydantic_ai.toolsets.function import FunctionToolset

from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.tools.standalone.catalog import (
    browse_search_categories,
    get_record_types,
    list_searches,
    list_transforms,
    lookup_phyletic_codes,
    search_example_plans,
    search_for_searches,
)
from pathfinder.ai.tools.standalone.catalog_discovery import (
    get_parameter_dependencies,
    get_parameter_options,
    get_search_overview,
    update_search_decision,
)
from pathfinder.ai.tools.standalone.gene import lookup_gene_records
from pathfinder.ai.tools.standalone.memory_tools import remember, search_memory
from pathfinder.ai.tools.standalone.research import literature_search, web_search
from pathfinder.ai.tools.standalone.strategy_graph import get_strategy
from pathfinder.ai.tools.standalone.think import think
from pathfinder.ai.tools.toolsets._dynamic import (
    DynamicEnumToolset,
    EnumOverrides,
)


def _discovery_enum_overrides(
    ctx: RunContext[AgentDeps],
) -> EnumOverrides:
    """Compute per-LLM-request enum constraints for the discovery toolset.

    The model's freedom narrows as the run progresses:

    * Cold start (nothing inspected): no enums; the model must browse.
    * After ``get_search_overview`` for any search: ``update_search_decision``
      and ``get_parameter_options`` constrain ``search_name`` to the
      inspected set.
    * Once any params are known: ``get_parameter_options.parameter_id``
      constrains to the flat union of all discovered params (the body
      still verifies the param belongs to the specific search via
      ``ModelRetry``).
    """
    state = ctx.deps.agent_state
    inspected = sorted(state.discovered_search_names())
    all_params = sorted(state.all_param_keys())
    overrides: EnumOverrides = {}
    if inspected:
        overrides[("update_search_decision", "search_name")] = inspected
        overrides[("get_parameter_options", "search_name")] = inspected
        overrides[("get_parameter_dependencies", "search_name")] = inspected
    if all_params:
        overrides[("get_parameter_options", "parameter_id")] = all_params
    return overrides


def build_toolset() -> AbstractToolset[AgentDeps]:
    """Build the discovery-phase toolset.

    Phase exit is handled by ``output_type=DiscoveryDecision`` on the
    discovery agent — no ``finish_*`` tool is exposed.

    The toolset is wrapped in :class:`DynamicEnumToolset` so the JSON
    schema for ``search_name`` and ``parameter_id`` arguments is
    rewritten before every LLM request to include an ``enum`` of the
    actually-discovered values. Strict mode at the OpenAI / Anthropic
    layer then prevents the model from emitting hallucinated identifiers
    at all.
    """
    base: FunctionToolset[AgentDeps] = FunctionToolset(
        tools=[
            get_record_types,
            search_for_searches,
            browse_search_categories,
            list_searches,
            list_transforms,
            lookup_phyletic_codes,
            search_example_plans,
            get_search_overview,
            update_search_decision,
            get_parameter_options,
            get_parameter_dependencies,
            web_search,
            literature_search,
            lookup_gene_records,
            get_strategy,
            think,
            search_memory,
            remember,
        ],
    )
    return DynamicEnumToolset(
        wrapped=base, build_overrides=_discovery_enum_overrides,
    )
