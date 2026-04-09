"""ToolResilience capability -- Layers 0-2.

Routes tool execution failures to the right recovery strategy:

  Layer 0 (prepare_tools): circuit breaker — removes tools past retry threshold
  Layer 1 (on_tool_execute_error): TRANSIENT → ModelRetry, SEMANTIC → directive,
    PERMANENT → unavailable directive, UNKNOWN → generic directive + log
  Layer 2 (on_node_run_error): UnexpectedModelBehavior → End with graceful message
"""

from __future__ import annotations

import traceback
from dataclasses import dataclass
from typing import Any

from pydantic_ai.capabilities.abstract import AbstractCapability
from pydantic_ai.exceptions import ModelRetry, UnexpectedModelBehavior
from pydantic_ai.messages import ToolCallPart
from pydantic_ai.tools import RunContext, ToolDefinition
from pydantic_graph.nodes import End

from pathfinder.ai.capabilities.error_classification import (
    ErrorCategory,
    build_error_directive,
    classify_error,
)
from pathfinder.ai.orchestration.deps import AgentDeps
from pathfinder.platform.errors import WDKError
from pathfinder.platform.logging import get_logger

_WDK_STATUS_NOT_FOUND = 404
_WDK_STATUS_UNPROCESSABLE = 422

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Search-related tool names that get context-specific 404 guidance
# ---------------------------------------------------------------------------

_SEARCH_LOOKUP_TOOLS = frozenset(
    {
        "get_search_overview",
        "get_parameter_options",
        "get_parameter_dependencies",
    }
)


# ---------------------------------------------------------------------------
# Next-action libraries
# ---------------------------------------------------------------------------

_NEXT_ACTIONS_WDK_404_SEARCH = [
    "Call search_for_searches(query=\"<describe what you need>\") to find the correct search name",
    "Call list_searches(record_type=\"transcript\") to see all available searches",
]

_NEXT_ACTIONS_WDK_422 = [
    "Call get_parameter_options for the rejected parameter to see valid values",
    "Use the exact value from the vocabulary, not free text",
]

_NEXT_ACTIONS_SEMANTIC_GENERIC = [
    "Check tool arguments and retry with corrected values",
]

_NEXT_ACTIONS_PERMANENT = [
    "Use alternative tools to accomplish the goal",
    "Ask the user if they can provide the information you were searching for",
]

_NEXT_ACTIONS_UNKNOWN = [
    "Try a different approach using other available tools",
    "If the task requires this tool, inform the user about the limitation",
]


# ---------------------------------------------------------------------------
# Semantic directive builders
# ---------------------------------------------------------------------------


def _semantic_directive(
    error: Exception,
    tool_name: str,
    args: dict[str, Any],
) -> str:
    """Return a context-specific directive for SEMANTIC errors."""
    if isinstance(error, WDKError):
        if error.status == _WDK_STATUS_NOT_FOUND and tool_name in _SEARCH_LOOKUP_TOOLS:
            return build_error_directive(
                error_type="SEARCH_NOT_FOUND",
                tool_name=tool_name,
                tool_args=args,
                detail=str(error),
                next_actions=_NEXT_ACTIONS_WDK_404_SEARCH,
                do_not="Do not retry with the same search name — it does not exist on this site",
            )
        if error.status == _WDK_STATUS_UNPROCESSABLE:
            return build_error_directive(
                error_type="INVALID_PARAMETER_VALUE",
                tool_name=tool_name,
                tool_args=args,
                detail=str(error),
                next_actions=_NEXT_ACTIONS_WDK_422,
                do_not="Do not pass free-text values for vocabulary parameters",
            )

    return build_error_directive(
        error_type="SEMANTIC_TOOL_ERROR",
        tool_name=tool_name,
        tool_args=args,
        detail=str(error),
        next_actions=_NEXT_ACTIONS_SEMANTIC_GENERIC,
        do_not="Do not retry with the same arguments without correcting them first",
    )


# ---------------------------------------------------------------------------
# ToolResilience capability
# ---------------------------------------------------------------------------


@dataclass
class ToolResilience(AbstractCapability[AgentDeps]):
    """Routes tool execution errors to the appropriate recovery strategy.

    Layer 0: prepare_tools — circuit breaker removes tools past the retry threshold
    Layer 1: on_tool_execute_error
      - TRANSIENT  → ModelRetry (pydantic-ai retries the call)
      - SEMANTIC   → structured directive string returned as tool result
      - PERMANENT  → service-unavailable directive
      - UNKNOWN    → generic directive + full stack trace in logs
    Layer 2: on_node_run_error — UnexpectedModelBehavior → End with graceful message
    """

    _CIRCUIT_BREAK_THRESHOLD: int = 3

    async def on_tool_execute_error(
        self,
        ctx: RunContext[AgentDeps],
        *,
        call: ToolCallPart,
        tool_def: ToolDefinition,
        args: dict[str, Any],
        error: Exception,
    ) -> Any:
        """Intercept tool execution errors and route by category."""
        tool_name = tool_def.name
        category = classify_error(error)

        if category == ErrorCategory.TRANSIENT:
            retry_message = (
                f"Transient error in {tool_name}: {error}. "
                "The service may be temporarily unavailable. Retrying."
            )
            raise ModelRetry(retry_message)

        if category == ErrorCategory.SEMANTIC:
            return _semantic_directive(error, tool_name, args)

        if category == ErrorCategory.PERMANENT:
            return build_error_directive(
                error_type="SERVICE_UNAVAILABLE",
                tool_name=tool_name,
                tool_args=args,
                detail=str(error),
                next_actions=_NEXT_ACTIONS_PERMANENT,
                do_not="Do not call this tool again — the service is permanently unavailable",
            )

        # UNKNOWN — log full stack trace, return generic directive
        logger.error(
            "Unknown tool error",
            tool_name=tool_name,
            error_type=type(error).__name__,
            traceback=traceback.format_exc(),
        )
        return build_error_directive(
            error_type="INTERNAL_TOOL_ERROR",
            tool_name=tool_name,
            tool_args=args,
            detail=f"{type(error).__name__}: {error}",
            next_actions=_NEXT_ACTIONS_UNKNOWN,
            do_not="Do not retry this exact call — an unexpected internal error occurred",
        )

    async def on_node_run_error(
        self,
        ctx: RunContext[AgentDeps],
        *,
        node: Any,
        error: Exception,
    ) -> Any:
        """Layer 2: intercept node-level failures.

        UnexpectedModelBehavior (e.g. infinite loops, malformed responses) terminates
        the run gracefully with a user-facing message rather than crashing.
        All other exceptions are re-raised so Layer 3 (on_run_error) can handle them.
        """
        if isinstance(error, UnexpectedModelBehavior):
            logger.warning(
                "UnexpectedModelBehavior in node run",
                node=repr(node),
                error=str(error),
            )
            return End(
                "I encountered repeated errors while trying to complete this step. "
                "The VEuPathDB service may be experiencing issues. "
                "Please try again in a moment, or rephrase your request."
            )
        raise error

    async def prepare_tools(
        self,
        ctx: RunContext[AgentDeps],
        tool_defs: list[ToolDefinition],
    ) -> list[ToolDefinition]:
        """Layer 0: circuit breaker — remove tools that have failed too many times.

        Tools whose retry count meets or exceeds _CIRCUIT_BREAK_THRESHOLD are
        removed from the tool list for this step, preventing infinite retry loops.
        """
        if not ctx.retries:
            return tool_defs

        filtered = [
            td
            for td in tool_defs
            if ctx.retries.get(td.name, 0) < self._CIRCUIT_BREAK_THRESHOLD
        ]

        removed = [td.name for td in tool_defs if td not in filtered]
        if removed:
            logger.warning(
                "Circuit breaker: removing tools past retry threshold",
                removed_tools=removed,
                threshold=self._CIRCUIT_BREAK_THRESHOLD,
            )

        return filtered
