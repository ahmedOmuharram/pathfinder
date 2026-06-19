"""Verification toolset registration assertions.

``optimize_search_parameters`` is a long-running durable tool exposed on the
verification sub-agent. It must be registered ``sequential=True`` (durable
tools suspend the graph via ``interrupt()`` and cannot share a tool batch)
and ``requires_approval=True`` (the SDK halts for user confirmation before a
~15-minute sweep runs). This test pins that contract.
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


def test_optimize_search_parameters_registered_with_approval_and_sequential() -> None:
    toolset = _unwrap_to_function_toolset(build_toolset())
    by_name = {t.name: t for t in toolset.tools.values()}
    assert "optimize_search_parameters" in by_name, (
        "optimize_search_parameters must be registered on the verification toolset."
    )
    tool = by_name["optimize_search_parameters"]
    assert tool.requires_approval is True, (
        "optimize_search_parameters must require approval — it launches a "
        "long-running, expensive sweep."
    )
    assert tool.sequential is True, (
        "durable tools must run sequential=True so their interrupt() does not "
        "orphan a sibling tool's return part."
    )


def test_other_durable_verification_tools_still_registered() -> None:
    toolset = _unwrap_to_function_toolset(build_toolset())
    tool_names = {t.name for t in toolset.tools.values()}
    assert "run_control_tests_on_step" in tool_names
    assert "run_gene_set_enrichment" in tool_names
