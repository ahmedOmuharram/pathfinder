"""Anti-thrash circuit breaker for repeated identical read-only tool calls.

After execution failure, the replanning agent can loop ``get_strategy`` ->
``get_plan`` -> ``get_strategy`` -> ... dozens of times with identical
arguments and no intervening state change, burning tokens until the context
limit.  This guard detects that pattern and returns a warning string
instead of executing the tool a third consecutive time.

Graph-modifying tool calls (even failed ones) reset the counter because
the model has reason to re-read after attempting modification.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

READ_ONLY_TOOLS: frozenset[str] = frozenset({
    "get_strategy",
    "get_plan",
    "get_step_preview",
    "get_step_results",
    "get_record_detail",
    "get_records",
    "get_attributes",
    "get_distribution",
    "search_catalog",
    "text_search",
})

GRAPH_MODIFYING_TOOLS: frozenset[str] = frozenset({
    "create_leaf_step",
    "create_combined_step",
    "create_transform_step",
    "update_step",
    "combine_steps",
    "apply_view_filter",
    "delete_view_filter",
    "update_search_config",
    "submit_plan",
    "update_plan",
    "finish_scoping",
    "finish_discovery",
    "finish_planning",
    "finish_execution",
    "finish_verification",
})

REPETITION_THRESHOLD: int = 3


def _args_fingerprint(args: object) -> str:
    """Hash tool args for comparison.

    Uses ``json.dumps(args, sort_keys=True, default=str)`` then
    sha256[:16] for a stable, compact fingerprint.
    """
    serialized = json.dumps(args, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()[:16]


@dataclass
class ToolRepetitionGuard:
    """Tracks consecutive identical read-only tool calls and blocks loops.

    Instantiate once per turn (lives on ``AgentDeps``). Each call to
    :meth:`check` returns ``None`` (proceed) or a warning string (blocked).
    """

    _last_tool: str = field(default="", init=False, repr=False)
    _last_fingerprint: str = field(default="", init=False, repr=False)
    _consecutive_count: int = field(default=0, init=False, repr=False)
    _total_blocked: int = field(default=0, init=False, repr=False)

    @property
    def total_blocked(self) -> int:
        """Count of times the guard fired (blocked a call)."""
        return self._total_blocked

    def _reset(self) -> None:
        """Reset tracking state."""
        self._last_tool = ""
        self._last_fingerprint = ""
        self._consecutive_count = 0

    def check(self, tool_name: str, tool_args: object) -> str | None:
        """Check whether a tool call should proceed or be blocked.

        Returns ``None`` to proceed, or a warning string to block.
        """
        # Graph-modifying tools always proceed and reset the counter.
        if tool_name in GRAPH_MODIFYING_TOOLS:
            self._reset()
            return None

        # Non-classified tools (not read-only, not modifying) reset and proceed.
        if tool_name not in READ_ONLY_TOOLS:
            self._reset()
            return None

        # Read-only tool: compute fingerprint and check for repetition.
        fingerprint = _args_fingerprint(tool_args)

        if tool_name == self._last_tool and fingerprint == self._last_fingerprint:
            self._consecutive_count += 1
        else:
            self._last_tool = tool_name
            self._last_fingerprint = fingerprint
            self._consecutive_count = 1

        if self._consecutive_count >= REPETITION_THRESHOLD:
            self._total_blocked += 1
            return (
                f"You have called {tool_name} {self._consecutive_count} times "
                f"consecutively with identical arguments and no intervening "
                f"state change. This is a loop. Either: (1) take a DIFFERENT "
                f"action to make progress, (2) call a graph-modifying tool to "
                f"change state, or (3) use finish_planning/finish_verification "
                f"to end the phase with what you have. Do NOT call {tool_name} "
                f"again with the same arguments."
            )

        return None

    def record_modifying_call(self, tool_name: str) -> None:
        """Explicitly reset the counter for a graph-modifying call.

        Call this when a modifying tool is invoked outside of :meth:`check`,
        e.g. from a post-execution hook.
        """
        if tool_name in GRAPH_MODIFYING_TOOLS:
            self._reset()
