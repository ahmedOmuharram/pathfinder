"""Error classification and directive formatting for AI tool resilience.

Provides:
- ``ErrorCategory`` — four-value StrEnum classifying exception types
- ``classify_error`` — maps any exception to an ``ErrorCategory``
- ``build_error_directive`` — formats a structured error directive string
  for consumption by the AI agent as tool-call feedback.
  Callers supply context-specific ``next_actions``, ``do_not``, and
  ``detail`` so the directive is actionable rather than generic.
"""

from __future__ import annotations

from enum import StrEnum

import httpx

from pathfinder.platform.errors import AppError, WDKError

# ---------------------------------------------------------------------------
# Category enum
# ---------------------------------------------------------------------------

_PERMANENT_PHRASES = (
    "not configured",
    "not available",
    "not enabled",
    "service is disabled",
)

# HTTP status threshold above which WDK errors are considered transient.
_WDK_SERVER_ERROR_THRESHOLD = 500

# Max chars for a single serialized argument value before truncation.
_MAX_ARG_VALUE_CHARS = 120

# Max chars for the entire rendered args string inside the TOOL() parens.
_MAX_ARGS_TOTAL_CHARS = 300


class ErrorCategory(StrEnum):
    """Broad classification of an exception for resilience routing."""

    TRANSIENT = "TRANSIENT"
    SEMANTIC = "SEMANTIC"
    PERMANENT = "PERMANENT"
    UNKNOWN = "UNKNOWN"


# ---------------------------------------------------------------------------
# classify_error
# ---------------------------------------------------------------------------


def _classify_runtime_error(error: RuntimeError) -> ErrorCategory:
    """Classify a RuntimeError as PERMANENT or UNKNOWN."""
    message = str(error).lower()
    if any(phrase in message for phrase in _PERMANENT_PHRASES):
        return ErrorCategory.PERMANENT
    return ErrorCategory.UNKNOWN


def classify_error(error: Exception) -> ErrorCategory:
    """Classify *error* into an ``ErrorCategory``.

    Classification is ordered so that more-specific types are checked first
    (WDKError before AppError, because WDKError is an AppError subclass).

    Rules
    -----
    WDKError status >= 500         → TRANSIENT
    WDKError status <  500         → SEMANTIC
    httpx.TimeoutException          → TRANSIENT
    httpx.ConnectError              → TRANSIENT
    OSError (incl. ConnectionError) → TRANSIENT
    AppError subclasses             → SEMANTIC
    RuntimeError "not configured" / "not available" /
                 "not enabled" / "service is disabled" → PERMANENT
    RuntimeError (other)            → UNKNOWN
    Everything else                 → UNKNOWN
    """
    if isinstance(error, WDKError):
        is_server_error = error.status >= _WDK_SERVER_ERROR_THRESHOLD
        return ErrorCategory.TRANSIENT if is_server_error else ErrorCategory.SEMANTIC

    if isinstance(error, AppError):
        return ErrorCategory.SEMANTIC

    if isinstance(error, (httpx.TimeoutException, httpx.ConnectError, OSError)):
        return ErrorCategory.TRANSIENT

    if isinstance(error, RuntimeError):
        return _classify_runtime_error(error)

    return ErrorCategory.UNKNOWN


# ---------------------------------------------------------------------------
# Directive formatting
# ---------------------------------------------------------------------------


def _sanitize_args(tool_args: dict[str, object]) -> str:
    """Render *tool_args* as a compact key=value string with truncation.

    Each individual value is truncated to ``_MAX_ARG_VALUE_CHARS`` characters.
    The total rendered string is truncated to ``_MAX_ARGS_TOTAL_CHARS``.
    """
    if not tool_args:
        return ""

    parts: list[str] = []
    for key, value in tool_args.items():
        rendered = repr(value)
        if len(rendered) > _MAX_ARG_VALUE_CHARS:
            rendered = rendered[:_MAX_ARG_VALUE_CHARS] + "..."
        parts.append(f"{key}={rendered}")

    joined = ", ".join(parts)
    if len(joined) > _MAX_ARGS_TOTAL_CHARS:
        joined = joined[:_MAX_ARGS_TOTAL_CHARS] + "..."

    return joined


def build_error_directive(
    *,
    error_type: str,
    tool_name: str,
    tool_args: dict[str, object],
    detail: str,
    next_actions: list[str],
    do_not: str,
) -> str:
    """Build a structured error directive string for agent feedback.

    Callers (e.g. ToolResilience) supply context-specific ``next_actions``,
    ``do_not``, and ``detail`` so guidance is actionable rather than generic.

    Format
    ------
    ERROR: {error_type}
    TOOL: {tool_name}({sanitized_args})
    DETAIL: {detail}
    NEXT_ACTIONS:
      1. {action1}
      2. {action2}
    DO NOT: {do_not}
    """
    args_str = _sanitize_args(tool_args)
    tool_call = f"{tool_name}({args_str})"

    numbered_actions = "\n".join(
        f"  {i + 1}. {action}" for i, action in enumerate(next_actions)
    )

    return (
        f"ERROR: {error_type}\n"
        f"TOOL: {tool_call}\n"
        f"DETAIL: {detail}\n"
        f"NEXT_ACTIONS:\n{numbered_actions}\n"
        f"DO NOT: {do_not}"
    )


def is_error_directive(content: object) -> bool:
    """True when a tool result is a structured error directive from
    ``build_error_directive`` (returned, not raised — so it rides a normal
    ``ToolReturnPart``). Used to render the step as failed rather than done."""
    return (
        isinstance(content, str)
        and content.startswith("ERROR: ")
        and "\nNEXT_ACTIONS:\n" in content
    )
