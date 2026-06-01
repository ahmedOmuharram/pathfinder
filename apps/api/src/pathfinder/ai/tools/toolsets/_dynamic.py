from __future__ import annotations

import copy
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any

from pydantic_ai.tools import AgentDepsT, RunContext
from pydantic_ai.toolsets.abstract import ToolsetTool
from pydantic_ai.toolsets.wrapper import WrapperToolset

from pathfinder.ai.graph.runtime import AgentDeps

EnumOverrides = dict[tuple[str, str], list[Any]]
EnumOverrideBuilder = Callable[[RunContext[AgentDepsT]], EnumOverrides]


@dataclass
class DynamicEnumToolset(WrapperToolset[AgentDepsT]):
    build_overrides: EnumOverrideBuilder[AgentDepsT]

    @property
    def id(self) -> str | None:
        return None

    async def get_tools(
        self,
        ctx: RunContext[AgentDepsT],
    ) -> dict[str, ToolsetTool[AgentDepsT]]:
        base_tools = await self.wrapped.get_tools(ctx)
        overrides = self.build_overrides(ctx)
        if not overrides:
            return base_tools
        return {
            name: _apply_enum_overrides(tool, name, overrides)
            for name, tool in base_tools.items()
        }


def _apply_enum_overrides(
    tool: ToolsetTool[AgentDepsT],
    tool_name: str,
    overrides: EnumOverrides,
) -> ToolsetTool[AgentDepsT]:
    # Deep-copies ``parameters_json_schema`` so the wrapped toolset's
    # cached definition isn't mutated.
    relevant = {
        arg: values
        for (t_name, arg), values in overrides.items()
        if t_name == tool_name and values
    }
    if not relevant:
        return tool
    new_schema = copy.deepcopy(tool.tool_def.parameters_json_schema)
    properties = new_schema.get("properties")
    if not isinstance(properties, dict):
        return tool
    changed = False
    for arg_name, values in relevant.items():
        prop = properties.get(arg_name)
        if not isinstance(prop, dict):
            continue
        # Sort to keep schema stable across requests for prompt caching.
        prop_with_enum = dict(prop)
        prop_with_enum["enum"] = sorted(values)
        properties[arg_name] = prop_with_enum
        changed = True
    if not changed:
        return tool
    new_tool_def = replace(tool.tool_def, parameters_json_schema=new_schema)
    return replace(tool, tool_def=new_tool_def)


def live_step_ids(deps: AgentDeps) -> list[str]:
    graph = deps.strategy_session.get_graph(None)
    if graph is None or not graph.steps:
        return []
    return sorted(graph.steps.keys())


def live_wdk_step_ids(deps: AgentDeps) -> list[int]:
    # ``wdk_step_id`` is only assigned after the step has been pushed to
    # WDK and built — local-only steps are excluded.
    sync_state = deps.strategy_session.sync_state
    if sync_state is None:
        return []
    mapping = sync_state.wdk_step_ids
    if not mapping:
        return []
    return sorted(set(mapping.values()))


__all__ = [
    "DynamicEnumToolset",
    "EnumOverrideBuilder",
    "EnumOverrides",
    "live_step_ids",
    "live_wdk_step_ids",
]
