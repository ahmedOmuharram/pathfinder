"""Dynamic instructions for the pydantic-ai phase agents.

Each function is registered via ``@agent.instructions`` and evaluated
before every model request, so the model always sees current state.
"""

from __future__ import annotations

from pydantic_ai.tools import RunContext

from pathfinder.ai.context.rendering import (
    render_graph_state,
)
from pathfinder.ai.orchestration.deps import AgentDeps
from pathfinder.ai.prompts.loader import load_system_prompt

# ---------------------------------------------------------------------------
# Static system prompt (loaded once at import, immutable)
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT_FULL = load_system_prompt(include_site_hints=True)
_SYSTEM_PROMPT_CONTINUATION = load_system_prompt(include_site_hints=False)


# ---------------------------------------------------------------------------
# Dynamic instruction functions
# ---------------------------------------------------------------------------


def base_system_prompt(ctx: RunContext[AgentDeps]) -> str:
    """Return the base system prompt text.

    On continuation turns (context_summary is set), skip site hints to
    save ~400 tokens — the model already has site context from the
    summary.
    """
    is_continuation = ctx.deps.context_summary is not None
    if is_continuation:
        return _SYSTEM_PROMPT_CONTINUATION
    return _SYSTEM_PROMPT_FULL


def pinned_context_summary(ctx: RunContext[AgentDeps]) -> str | None:
    """Return the cross-turn context summary if available.

    Compressed summary of previous turns, re-evaluated each model request.
    """
    return ctx.deps.context_summary


def pinned_approved_plan(ctx: RunContext[AgentDeps]) -> str | None:
    """Return the approved plan as execution instructions if available.

    When a plan has been approved, this pins the exact tool calls the
    model should execute so it does not re-discover or re-plan.
    """
    return ctx.deps.approved_plan


def pinned_graph_state(ctx: RunContext[AgentDeps]) -> str | None:
    """Return the current strategy graph state as a compact text summary.

    Re-evaluated before every model request so the model always sees
    the latest graph (step counts, WDK IDs, validation errors) without
    needing the full JSON in each tool result.
    """
    graph = ctx.deps.strategy_session.get_graph(None)
    if not graph or not graph.steps:
        return None
    return render_graph_state(graph)


def mentioned_context(ctx: RunContext[AgentDeps]) -> str | None:
    """Return user-mentioned context (e.g. selected nodes) if available."""
    return ctx.deps.mentioned_context


# ---------------------------------------------------------------------------
# Registration helper
# ---------------------------------------------------------------------------

# All instruction functions in registration order.  The caller (agent
# factory) iterates this list and calls ``agent.instructions(fn)`` for
# each.
ALL_INSTRUCTIONS: list[object] = [
    base_system_prompt,
    pinned_context_summary,
    pinned_approved_plan,
    pinned_graph_state,
    mentioned_context,
]
