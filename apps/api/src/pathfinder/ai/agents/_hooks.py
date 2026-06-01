"""Post-tool-execution hooks.

Today this file contains a single hook: ``apply_discovery_hook``, which
parses the result of ``get_search_overview`` and registers the search in
``AgentToolState`` so downstream phases (planning, execution) can see
which searches the discovery agent committed to.

The auto-build hook chain (``apply_auto_build_hook``, ``_auto_build``,
``_apply_single_root_build``, ``_GRAPH_MUTATING_TOOLS``, etc.) was deleted
in SC-D22. Persistence and WDK push are now driven directly by the
declarative ``build_strategy`` tool via
``services/strategies/spec_build.py``.
"""

from __future__ import annotations

from typing import Any

from pydantic import ConfigDict, Field, ValidationError
from pydantic_ai.messages import ToolCallPart
from pydantic_ai.tools import RunContext, ToolDefinition

from pathfinder.ai.agents.state import SearchOverview
from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.platform.logging import get_logger
from pathfinder.platform.pydantic_base import CamelModel

logger = get_logger(__name__)


class _ParamEntry(CamelModel):
    model_config = ConfigDict(extra="ignore")

    name: str = ""


class _RawSearchOverview(CamelModel):
    """Lenient parser for ``get_search_overview`` results."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    searchName: str = ""
    displayName: str = ""
    recordType: str = ""
    description: str = ""
    required: list[_ParamEntry] = Field(default_factory=list)
    optional: list[_ParamEntry] = Field(default_factory=list)


def _track_search_discovery(deps: AgentDeps, result_text: str) -> None:
    try:
        raw = _RawSearchOverview.model_validate_json(result_text)
    except ValidationError, ValueError:
        return
    if not raw.searchName:
        return

    required_names = [p.name for p in raw.required]
    all_params = list(required_names)
    all_params.extend(p.name for p in raw.optional)

    overview = SearchOverview(
        search_name=raw.searchName,
        display_name=raw.displayName or raw.searchName,
        record_type=raw.recordType or "transcript",
        description=raw.description,
        parameter_names=all_params,
        required_params=required_names,
    )
    deps.agent_state.register_search(raw.searchName, overview)


async def apply_discovery_hook(
    ctx: RunContext[AgentDeps],
    /,
    *,
    call: ToolCallPart,
    tool_def: ToolDefinition,
    args: dict[str, Any],
    result: Any,
) -> Any:
    """Register the search in agent state when ``get_search_overview`` returns."""
    if call.tool_name != "get_search_overview":
        return result
    if isinstance(result, str):
        _track_search_discovery(ctx.deps, result)
    return result


__all__ = ["apply_discovery_hook"]
