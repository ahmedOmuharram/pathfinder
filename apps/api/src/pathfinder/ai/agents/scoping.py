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
from pathfinder.ai.agents._phase_decisions import ScopingDecision
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

5. **Save the frame**: Call `set_problem_frame` exactly once before producing \
your final output. The problem frame you save should match the \
`problem_frame` field of the ScopingDecision you return.

## Final Output

When you have gathered enough context, produce a `ScopingDecision` as your \
final output. Do NOT call any `finish_*` tool; those tools no longer exist.

Choose `next_action` based on what you found:
  - `advance_to_discovery`: user intent is clear and you have at least one \
candidate search (list concrete names in `discovered_searches`).
  - `advance_to_planning`: user intent is so constrained that discovery \
would be superfluous.
  - `need_more_input`: you cannot proceed without the user clarifying \
something. Explain what you need in `reason`.

Populate every field:
  - `problem_frame`: concise problem statement (organism, record type, \
constraints, success criteria).
  - `discovered_searches`: WDK search names already known to be relevant \
(empty list if none).
  - `reason`: one-to-two sentence justification for `next_action`.

## Boundaries

- Do NOT use WDK catalog searches, WDK parameter tools, strategy-editing \
tools, or plan tools in this phase.
- Do NOT create, submit, approve, or execute a plan.
- If the request is clear enough, state the problem frame and move forward.
- If it is not clear enough, ask the blocking questions in plain language, \
then return a ScopingDecision with `next_action="need_more_input"`. The next \
user answer will restart scoping with the saved frame.
"""

# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

scoping_agent: Agent[AgentDeps, ScopingDecision] = Agent(
    "openai:gpt-4.1-mini",
    output_type=ScopingDecision,
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
