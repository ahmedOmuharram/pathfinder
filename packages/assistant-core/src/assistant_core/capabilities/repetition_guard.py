"""Anti-thrash circuit breaker as a pydantic-ai capability hook.

After a tool result an agent can fall into a tight loop reading the same
read-only tool. ``request_limit`` eventually catches this, but by then
hundreds of tokens are burned. The guard blocks the Nth consecutive identical
read-only call with a warning string that nudges the model to take a different
action.

The tool names are the product's, so the guard is constructed with them; a
guard built with no vocabulary never blocks. The state lives in
:class:`ToolRepetitionGuard` on the agent's deps, so tool functions do not
need to know the check exists.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic_ai.messages import ToolCallPart
from pydantic_ai.tools import RunContext, ToolDefinition

DEFAULT_REPETITION_THRESHOLD: int = 3


def _args_fingerprint(args: object) -> str:
    serialized = json.dumps(args, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()[:16]


@dataclass
class ToolRepetitionGuard:
    """Tracks consecutive identical read-only tool calls and blocks loops."""

    read_only_tools: frozenset[str] = frozenset()
    graph_modifying_tools: frozenset[str] = frozenset()
    threshold: int = DEFAULT_REPETITION_THRESHOLD
    _last_tool: str = field(default="", init=False, repr=False)
    _last_fingerprint: str = field(default="", init=False, repr=False)
    _consecutive_count: int = field(default=0, init=False, repr=False)
    _total_blocked: int = field(default=0, init=False, repr=False)

    @property
    def total_blocked(self) -> int:
        return self._total_blocked

    def _reset(self) -> None:
        self._last_tool = ""
        self._last_fingerprint = ""
        self._consecutive_count = 0

    def check(self, tool_name: str, tool_args: object) -> str | None:
        """Return ``None`` to proceed, or a warning string to block the call."""
        if tool_name in self.graph_modifying_tools:
            self._reset()
            return None
        if tool_name not in self.read_only_tools:
            self._reset()
            return None

        fingerprint = _args_fingerprint(tool_args)
        if tool_name == self._last_tool and fingerprint == self._last_fingerprint:
            self._consecutive_count += 1
        else:
            self._last_tool = tool_name
            self._last_fingerprint = fingerprint
            self._consecutive_count = 1

        if self._consecutive_count >= self.threshold:
            self._total_blocked += 1
            return (
                f"You have called {tool_name} {self._consecutive_count} times "
                f"consecutively with identical arguments and no intervening "
                f"state change. This is a loop. Either: (1) take a DIFFERENT "
                f"action to make progress, (2) call a graph-modifying tool to "
                f"change state, or (3) end the phase with your output_type "
                f"decision. Do NOT call {tool_name} again with these args."
            )
        return None


async def repetition_guard_hook(
    ctx: RunContext[Any],
    /,
    *,
    call: ToolCallPart,
    tool_def: ToolDefinition,
    args: dict[str, Any],
    handler: Callable[[dict[str, Any]], Awaitable[Any]],
) -> Any:
    """Wrap a tool execution; short-circuit on detected repetition.

    Registered via ``Hooks(tool_execute=repetition_guard_hook)`` on agents
    whose toolsets contain read-only inspectors. State lives on
    ``ctx.deps.tool_repetition_guard`` (fresh per deps instance).
    """
    del tool_def
    guard = getattr(ctx.deps, "tool_repetition_guard", None)
    if guard is None:
        return await handler(args)
    warning = guard.check(call.tool_name, args)
    if warning is not None:
        return warning
    return await handler(args)
