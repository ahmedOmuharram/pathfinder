from __future__ import annotations

from pydantic_ai import Agent
from pydantic_ai.capabilities import Hooks, Thinking
from pydantic_ai.tools import RunContext
from pydantic_ai.usage import UsageLimits

from pathfinder.ai.agents._hooks import apply_auto_build_hook
from pathfinder.ai.agents._instructions import (
    base_system_prompt,
    pinned_graph_state,
)
from pathfinder.ai.agents._phase_decisions import ExecutionDecision
from pathfinder.ai.capabilities.repetition_guard import repetition_guard_hook
from pathfinder.ai.capabilities.resilience import ToolResilience
from pathfinder.ai.capabilities.security import SecurityGuardrail
from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.tools.toolsets.execution import build_toolset

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

## Final Output

Your user-facing prose is the visible response — keep it brief and factual: \
report what completed, what failed, or which exact step is blocked. When \
the plan has been fully applied (or cannot be), return an `ExecutionDecision` \
whose only field is `next_action`:
  - `advance_to_verification`: all planned steps were applied successfully.
  - `retry`: one or more steps failed but retrying with adjusted parameters \
is likely to succeed.
  - `abort`: the plan is fundamentally broken and verification cannot \
proceed (the orchestrator will typically redirect to replanning).

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
- Do NOT ask the user follow-up questions such as "Would you like me to..." \
or "What next?" while execution is already running.
- If you emit text during execution, keep it brief and factual: report only \
what completed, what failed, or which exact step is blocked. Do not narrate \
hypothetical next actions.
"""

_execution_hooks: Hooks[AgentDeps] = Hooks(
    after_tool_execute=apply_auto_build_hook,
    tool_execute=repetition_guard_hook,
)

execution_agent: Agent[AgentDeps, ExecutionDecision] = Agent(
    "openai:gpt-4.1-mini",
    output_type=ExecutionDecision,
    deps_type=AgentDeps,
    instructions=_EXECUTION_INSTRUCTIONS,
    toolsets=[build_toolset()],
    capabilities=[
        ToolResilience(),
        _execution_hooks,
        Thinking(effort="medium"),
        SecurityGuardrail(),
    ],
    retries=3,
    description="Builds WDK strategies by executing planned operations",
    name="execution",
    defer_model_check=True,
)


@execution_agent.instructions
def _base_system_prompt(ctx: RunContext[AgentDeps]) -> str:
    return base_system_prompt(ctx)


@execution_agent.instructions
def _pinned_graph_state(ctx: RunContext[AgentDeps]) -> str | None:
    return pinned_graph_state(ctx)


EXECUTION_USAGE_LIMITS = UsageLimits(
    request_limit=200,
    total_tokens_limit=500_000,
)
