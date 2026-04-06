"""HookedFunctionToolset — FunctionToolset with post-execution hook support.

Provides ``HookedFunctionToolset``, a subclass of ``FunctionToolset`` that
applies a sequence of async post-tool callbacks after each tool call.  Each
callback receives ``(tool_name, result, ctx)`` and returns the (potentially
modified) result.

Usage::

    toolset = HookedFunctionToolset(
        tools=[...],
        post_hooks=[apply_discovery_hook, apply_auto_build_hook],
    )
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from pydantic_ai._run_context import AgentDepsT
from pydantic_ai.tools import RunContext, Tool, ToolFuncEither
from pydantic_ai.toolsets.abstract import ToolsetTool
from pydantic_ai.toolsets.function import FunctionToolset, FunctionToolsetTool

PostHook = Callable[[str, Any, RunContext[AgentDepsT]], Awaitable[Any]]
"""A post-tool hook: receives (tool_name, result, ctx) and returns result."""


class HookedFunctionToolset(FunctionToolset[AgentDepsT]):
    """A ``FunctionToolset`` that runs async post-tool callbacks after each call.

    The hooks are applied in order. Each hook may transform the result, which
    flows into the next hook and ultimately back to the LLM.
    """

    _post_hooks: list[PostHook[AgentDepsT]]

    def __init__(
        self,
        tools: Sequence[Tool[AgentDepsT] | ToolFuncEither[AgentDepsT, ...]] = [],
        *,
        post_hooks: Sequence[PostHook[AgentDepsT]] = (),
        max_retries: int = 1,
    ) -> None:
        super().__init__(tools=tools, max_retries=max_retries)
        self._post_hooks = list(post_hooks)

    async def call_tool(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: RunContext[AgentDepsT],
        tool: ToolsetTool[AgentDepsT],
    ) -> Any:
        if not isinstance(tool, FunctionToolsetTool):
            msg = f"Expected FunctionToolsetTool, got {type(tool).__name__}"
            raise TypeError(msg)
        result = await tool.call_func(tool_args, ctx)
        for hook in self._post_hooks:
            result = await hook(name, result, ctx)
        return result
