"""Discovery-phase toolset — 14 tools for exploring searches, literature, and catalogs."""

from pydantic_ai.toolsets.function import FunctionToolset

from pathfinder.ai.orchestration.deps import AgentDeps
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
)
from pathfinder.ai.tools.standalone.gene import lookup_gene_records
from pathfinder.ai.tools.standalone.research import literature_search, web_search
from pathfinder.ai.tools.standalone.strategy_graph import get_strategy
from pathfinder.ai.tools.standalone.think import think


def build_toolset() -> FunctionToolset[AgentDeps]:
    """Build the discovery-phase toolset.

    Phase exit is handled by ``output_type=DiscoveryDecision`` on the
    discovery agent — no ``finish_*`` tool is exposed.
    """
    return FunctionToolset(
        tools=[
            get_record_types,
            search_for_searches,
            browse_search_categories,
            list_searches,
            list_transforms,
            lookup_phyletic_codes,
            search_example_plans,
            get_search_overview,
            get_parameter_options,
            get_parameter_dependencies,
            web_search,
            literature_search,
            lookup_gene_records,
            get_strategy,
            think,
        ],
    )
