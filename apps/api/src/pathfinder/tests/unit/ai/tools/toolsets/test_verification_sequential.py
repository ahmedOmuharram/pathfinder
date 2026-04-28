from __future__ import annotations

from pydantic_ai.toolsets.function import FunctionToolset
from pydantic_ai.toolsets.wrapper import WrapperToolset

from pathfinder.ai.tools.toolsets.verification import build_toolset

_DURABLE_TOOLS = {
    "run_control_tests_on_step",
    "run_gene_set_enrichment",
}


def _unwrap_to_function_toolset(toolset: object) -> FunctionToolset:
    """Recursively unwrap ``WrapperToolset`` layers to reach the
    underlying ``FunctionToolset``. ``build_toolset`` now returns a
    ``DynamicEnumToolset`` (a wrapper) — drill through to get at the
    raw tool registrations the test cares about."""
    while isinstance(toolset, WrapperToolset):
        toolset = toolset.wrapped
    assert isinstance(toolset, FunctionToolset)
    return toolset


def test_every_durable_tool_is_sequential() -> None:
    toolset = _unwrap_to_function_toolset(build_toolset())
    tools_by_name = {t.name: t for t in toolset.tools.values()}
    missing = _DURABLE_TOOLS - tools_by_name.keys()
    assert not missing, f"durable tools missing from verification toolset: {missing}"
    for name in _DURABLE_TOOLS:
        tool = tools_by_name[name]
        assert tool.tool_def.sequential is True, (
            f"durable tool {name!r} must be registered with sequential=True "
            "so GraphInterrupt doesn't cancel sibling tool returns"
        )
