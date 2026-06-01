"""Verification toolset registration assertions.

The verification sub-agent no longer exposes ``optimize_search_parameters``
directly. This test pins the contract so the tool can't sneak back in via
auto-import or copy-paste.
"""

from __future__ import annotations

from pydantic_ai.toolsets.function import FunctionToolset
from pydantic_ai.toolsets.wrapper import WrapperToolset

from pathfinder.ai.tools.toolsets.verification import build_toolset


def _unwrap_to_function_toolset(toolset: object) -> FunctionToolset:
    while isinstance(toolset, WrapperToolset):
        toolset = toolset.wrapped
    assert isinstance(toolset, FunctionToolset)
    return toolset


def test_optimize_search_parameters_not_in_verification_toolset() -> None:
    toolset = _unwrap_to_function_toolset(build_toolset())
    tool_names = {t.name for t in toolset.tools.values()}
    assert "optimize_search_parameters" not in tool_names, (
        "optimize_search_parameters must NOT be registered on the verification toolset."
    )


def test_other_durable_verification_tools_still_registered() -> None:
    toolset = _unwrap_to_function_toolset(build_toolset())
    tool_names = {t.name for t in toolset.tools.values()}
    # Removal was scoped to the optimization tool. The other long-running
    # verification tools are still part of the in-graph toolset.
    assert "run_control_tests_on_step" in tool_names
    assert "run_gene_set_enrichment" in tool_names
