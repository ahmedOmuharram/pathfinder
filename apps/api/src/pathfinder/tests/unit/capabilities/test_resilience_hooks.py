"""Tests for hook interaction with error payloads from ToolResilience."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai.messages import ToolCallPart
from pydantic_ai.tools import ToolDefinition

from pathfinder.ai.agents._hooks import apply_auto_build_hook


def _make_ctx_with_graph() -> MagicMock:
    ctx: MagicMock = MagicMock()
    ctx.deps = MagicMock()
    graph = MagicMock()
    graph.roots = {1}
    graph.steps = {1: MagicMock(display_name="Step 1", search_name="GenesByTaxon")}
    ctx.deps.strategy_session.get_graph.return_value = graph
    return ctx


def _make_call(tool_name: str = "create_leaf_step") -> ToolCallPart:
    return ToolCallPart(tool_name=tool_name, args="{}", tool_call_id="tc_1")


def _make_tool_def(name: str = "create_leaf_step") -> ToolDefinition:
    return ToolDefinition(name=name, description="test", parameters_json_schema={})


# ---------------------------------------------------------------------------
# TestAutoBuildhookErrorGuard
# ---------------------------------------------------------------------------


class TestAutoBuildhookErrorGuard:
    """apply_auto_build_hook must skip auto-build when the result is an error payload."""

    @pytest.mark.asyncio
    async def test_skips_auto_build_for_error_directive(self) -> None:
        """Error-as-directive strings (start with 'ERROR:') must bypass auto-build."""
        ctx = _make_ctx_with_graph()
        error_result = "ERROR: WDKError (SEMANTIC)\nTOOL: create_leaf_step\nDETAIL: bad param"

        with patch(
            "pathfinder.ai.agents._hooks._apply_single_root_build",
            new_callable=AsyncMock,
        ) as mock_build:
            returned = await apply_auto_build_hook(
                ctx,
                call=_make_call("create_leaf_step"),
                tool_def=_make_tool_def("create_leaf_step"),
                args={},
                result=error_result,
            )

        mock_build.assert_not_called()
        assert returned == error_result

    @pytest.mark.asyncio
    async def test_skips_auto_build_for_json_error_payload(self) -> None:
        """JSON payloads with 'ok': false must bypass auto-build."""
        ctx = _make_ctx_with_graph()
        error_result = '{"ok": false, "code": "WDK_ERROR", "message": "Failed"}'

        with patch(
            "pathfinder.ai.agents._hooks._apply_single_root_build",
            new_callable=AsyncMock,
        ) as mock_build:
            returned = await apply_auto_build_hook(
                ctx,
                call=_make_call("create_leaf_step"),
                tool_def=_make_tool_def("create_leaf_step"),
                args={},
                result=error_result,
            )

        mock_build.assert_not_called()
        assert returned == error_result

    @pytest.mark.asyncio
    async def test_non_graph_mutating_tool_passes_through(self) -> None:
        """Non-graph-mutating tools are returned unchanged regardless of content."""
        ctx = _make_ctx_with_graph()
        # Even an error string — doesn't matter, non-graph-mutating tools skip all logic
        any_result = "ERROR: something happened"

        with patch(
            "pathfinder.ai.agents._hooks._apply_single_root_build",
            new_callable=AsyncMock,
        ) as mock_build:
            returned = await apply_auto_build_hook(
                ctx,
                call=_make_call("get_strategy"),
                tool_def=_make_tool_def("get_strategy"),
                args={},
                result=any_result,
            )

        mock_build.assert_not_called()
        assert returned == any_result
