"""Research-specialist toolset.

Catalog browsing + read-only data peek + external knowledge (web /
literature) + memory + reasoning + the specialist-only exit tool. No
strategy mutations, no durable tools.
"""

from pydantic_ai.toolsets.abstract import AbstractToolset
from pydantic_ai.toolsets.function import FunctionToolset

from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.tools.standalone.catalog import (
    browse_search_categories,
    get_record_types,
    list_searches,
    search_for_searches,
)
from pathfinder.ai.tools.standalone.catalog_discovery import (
    get_parameter_options,
    get_search_overview,
)
from pathfinder.ai.tools.standalone.execution import get_estimated_size
from pathfinder.ai.tools.standalone.exit_specialist import exit_specialist
from pathfinder.ai.tools.standalone.memory_tools import remember, search_memory
from pathfinder.ai.tools.standalone.research import (
    literature_search,
    web_search,
)
from pathfinder.ai.tools.standalone.results import get_sample_records
from pathfinder.ai.tools.standalone.think import think


def build_research_toolset() -> AbstractToolset[AgentDeps]:
    return FunctionToolset(
        tools=[
            # Catalog browsing
            get_record_types,
            list_searches,
            browse_search_categories,
            search_for_searches,
            get_search_overview,
            get_parameter_options,
            # Data peek (the system prompt nudges to prefer literature
            # for biological knowledge; only reach for these when the user
            # explicitly asks what the data looks like)
            get_sample_records,
            get_estimated_size,
            # External knowledge
            web_search,
            literature_search,
            # Cross-cutting
            think,
            search_memory,
            remember,
            # Specialist-only exit
            exit_specialist,
        ],
    )
