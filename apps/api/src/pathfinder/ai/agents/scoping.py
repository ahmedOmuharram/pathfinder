"""Scoping-phase agent — frames the user's research problem before WDK discovery.

This agent handles the first phase of the PathFinder pipeline: clarifying the
biological intent, optionally doing non-WDK research, and deciding whether the
request is ready for WDK catalog discovery.
"""

from __future__ import annotations

from pydantic_ai import Agent
from pydantic_ai.capabilities import Thinking
from pydantic_ai.tools import RunContext
from pydantic_ai.usage import UsageLimits

from pathfinder.ai.agents._instructions import (
    base_system_prompt,
    mentioned_context,
    pinned_context_summary,
    pinned_graph_state,
    pinned_problem_frame,
)
from pathfinder.ai.capabilities.resilience import ToolResilience
from pathfinder.ai.capabilities.security import SecurityGuardrail
from pathfinder.ai.orchestration.deps import AgentDeps
from pathfinder.ai.tools.toolsets.scoping import build_toolset

# ---------------------------------------------------------------------------
# Static instructions
# ---------------------------------------------------------------------------

_SCOPING_INSTRUCTIONS = """\
You are the Scoping Agent for PathFinder, a research accelerator for \
VEuPathDB pathogen databases. Your role is to frame the user's biological \
problem before the system starts WDK catalog discovery.

## Your Responsibilities

1. **Clarify the research intent**: Convert the user's request into a concise \
problem statement with organism scope, target record type if known, biological \
entities, inclusion/exclusion criteria, and success criteria.

2. **Ask only blocking questions**: If WDK discovery would likely choose the \
wrong organism, record type, data source, threshold, or biological definition, \
ask 1-3 blocking questions. Do not ask questions just to sound thorough.

3. **Use non-WDK research when needed**: Use `web_search` or \
`literature_search` only when external biological context would materially \
improve the problem frame. Keep notes short and source-grounded.

4. **Inspect current work when relevant**: Use `get_strategy` if the user is \
editing or extending an existing strategy.

5. **Save the frame**: Call `set_problem_frame` exactly once before your final \
answer. Set `ready_for_wdk_discovery` to true only when discovery can proceed \
without a risky guess.

6. **End the phase explicitly**: Call `finish_scoping` exactly once as your \
last tool call. Use `decision="ask_user"` when you need a user answer before \
WDK discovery. Use `decision="continue_to_discovery"` only when the request is \
ready to move forward.

## Boundaries

- Do NOT use WDK catalog searches, WDK parameter tools, strategy-editing tools, \
or plan tools in this phase.
- Do NOT create, submit, approve, or execute a plan.
- If the request is clear enough, state the problem frame and move forward.
- If it is not clear enough, ask the blocking questions in plain language, call \
`finish_scoping(decision="ask_user", ...)`, and stop. The next user answer \
will restart scoping with the saved frame.
"""

# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

scoping_agent: Agent[AgentDeps, str] = Agent(
    "anthropic:claude-sonnet-4-5",
    deps_type=AgentDeps,
    instructions=_SCOPING_INSTRUCTIONS,
    toolsets=[build_toolset()],
    capabilities=[ToolResilience(), Thinking(effort="medium"), SecurityGuardrail()],
    retries=3,
    description="Frames the biological problem before WDK discovery",
    name="scoping",
    defer_model_check=True,
)


@scoping_agent.instructions
def _base_system_prompt(ctx: RunContext[AgentDeps]) -> str:
    return base_system_prompt(ctx)


@scoping_agent.instructions
def _pinned_context_summary(ctx: RunContext[AgentDeps]) -> str | None:
    return pinned_context_summary(ctx)


@scoping_agent.instructions
def _pinned_problem_frame(ctx: RunContext[AgentDeps]) -> str | None:
    return pinned_problem_frame(ctx)


@scoping_agent.instructions
def _pinned_graph_state(ctx: RunContext[AgentDeps]) -> str | None:
    return pinned_graph_state(ctx)


@scoping_agent.instructions
def _mentioned_context(ctx: RunContext[AgentDeps]) -> str | None:
    return mentioned_context(ctx)


# ---------------------------------------------------------------------------
# Default usage limits
# ---------------------------------------------------------------------------

SCOPING_USAGE_LIMITS = UsageLimits(
    request_limit=25,
    total_tokens_limit=250_000,
)
