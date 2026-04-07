"""Execution-phase agent — builds and edits WDK strategies.

This agent follows the plan produced by the planning agent, executing
strategy operations (create_leaf_step, combine_steps, transform_step,
etc.) one at a time. The orchestrator calls this agent per-step with a
FilteredToolset scoped to the tools needed for that step; the agent
itself is configured with the full execution toolset as default.
"""

from __future__ import annotations

from pydantic_ai import Agent
from pydantic_ai.capabilities import Hooks, Thinking
from pydantic_ai.tools import RunContext
from pydantic_ai.usage import UsageLimits

from veupath_chatbot.ai.agents._hooks import apply_auto_build_hook
from veupath_chatbot.ai.agents._instructions import (
    base_system_prompt,
    mentioned_context,
    pinned_approved_plan,
    pinned_context_summary,
    pinned_graph_state,
)
from veupath_chatbot.ai.capabilities.security import SecurityGuardrail
from veupath_chatbot.ai.orchestration.deps import AgentDeps
from veupath_chatbot.ai.tools.toolsets.execution import build_toolset

# ---------------------------------------------------------------------------
# Static instructions
# ---------------------------------------------------------------------------

_EXECUTION_INSTRUCTIONS = """\
You are the Execution Agent for PathFinder. You receive a concrete plan \
and execute it step-by-step against the WDK strategy graph.

## Your Responsibilities

1. **Follow the plan exactly**: Execute each planned operation using the \
provided tools. Do not deviate from the plan unless a step fails.

2. **Handle failures gracefully**: If a tool call fails (WDK validation \
error, parameter rejection), attempt to fix it using `update_step`. If \
the fix fails, report the error clearly so the orchestrator can decide \
whether to retry or escalate.

3. **Respect the graph**: Use `get_strategy` to verify graph state after \
operations. The auto-build hook handles WDK push, sync, and gene set \
creation automatically — you do not need to trigger these manually.

## Guidelines

- One operation at a time. Create a leaf step, verify it succeeded, then \
move to the next planned step.
- Parameter values come from the plan. Do not re-discover or re-infer \
parameter values — the planning agent already determined them.
- When combining steps, reference step IDs from the current graph (visible \
via the pinned graph state), not from the plan's placeholder IDs.
- Use `rename_strategy` to set the strategy name if the plan specifies one.
- Do NOT explore the catalog or create plans — those phases are complete.
- Do NOT run analysis or export results — that is the verification agent's job.
"""

# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

_execution_hooks: Hooks[AgentDeps] = Hooks(after_tool_execute=apply_auto_build_hook)

execution_agent: Agent[AgentDeps, str] = Agent(
    "anthropic:claude-sonnet-4-5",
    deps_type=AgentDeps,
    instructions=_EXECUTION_INSTRUCTIONS,
    toolsets=[build_toolset()],
    capabilities=[_execution_hooks, Thinking(effort="medium"), SecurityGuardrail()],
    description="Builds WDK strategies by executing planned operations",
    name="execution",
    defer_model_check=True,
)


@execution_agent.instructions
def _base_system_prompt(ctx: RunContext[AgentDeps]) -> str:
    return base_system_prompt(ctx)


@execution_agent.instructions
def _pinned_context_summary(ctx: RunContext[AgentDeps]) -> str | None:
    return pinned_context_summary(ctx)


@execution_agent.instructions
def _pinned_approved_plan(ctx: RunContext[AgentDeps]) -> str | None:
    return pinned_approved_plan(ctx)


@execution_agent.instructions
def _pinned_graph_state(ctx: RunContext[AgentDeps]) -> str | None:
    return pinned_graph_state(ctx)


@execution_agent.instructions
def _mentioned_context(ctx: RunContext[AgentDeps]) -> str | None:
    return mentioned_context(ctx)


# ---------------------------------------------------------------------------
# Default usage limits
# ---------------------------------------------------------------------------

EXECUTION_USAGE_LIMITS = UsageLimits(
    request_limit=3,
    total_tokens_limit=30_000,
)

EXECUTION_RECOVERY_LIMITS = UsageLimits(
    request_limit=5,
    total_tokens_limit=50_000,
)
