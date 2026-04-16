from __future__ import annotations

from pydantic_ai import Agent
from pydantic_ai.capabilities import Thinking
from pydantic_ai.tools import RunContext
from pydantic_ai.usage import UsageLimits

from pathfinder.ai.agents._instructions import (
    base_system_prompt,
    pinned_graph_state,
    pinned_problem_frame,
    pinned_user_memories,
)
from pathfinder.ai.capabilities.resilience import ToolResilience
from pathfinder.ai.capabilities.security import SecurityGuardrail
from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.tools.toolsets.scoping import build_toolset

_SCOPING_INSTRUCTIONS = """\
You are the Scoping Agent for PathFinder, a research accelerator for \
VEuPathDB pathogen databases. Your role is to frame the user's biological \
problem before the system starts WDK catalog discovery.

## Your Responsibilities

1. **Clarify the research intent**: Speak to the user directly in prose — \
confirm the problem, state any assumptions, and name the next step. Never \
restate, quote, or paraphrase the user's literal question — their message \
is already visible above yours.

2. **Ask only blocking questions**: If WDK discovery would likely choose the \
wrong organism, record type, data source, threshold, or biological definition, \
ask 1-3 blocking questions. Do not ask questions just to sound thorough.

3. **Use non-WDK research when needed**: Use `web_search` or \
`literature_search` only when external biological context would materially \
improve the problem frame. Keep notes short and source-grounded.

4. **Inspect current work when relevant**: Use `get_strategy` if the user is \
editing or extending an existing strategy.

5. **Save the frame**: Call `set_problem_frame` exactly once before ending \
your turn — it captures the authoritative problem statement that downstream \
phases read.

## Output

End your turn with concise prose describing what you did (assumptions, \
blocking questions, or the framed problem statement). A supervisor will read \
your prose and decide whether to continue to discovery, skip straight to \
planning, or end the turn to wait for the user. You do not route; you write.

NEVER skip the prose. A reply that is only tool calls with no visible text \
is a failure — the user sees a blank assistant message.

## Boundaries

- Do NOT use WDK catalog searches, WDK parameter tools, strategy-editing \
tools, or plan tools in this phase.
- Do NOT create, submit, approve, or execute a plan.
- If the request is clear enough, state the problem frame and let the \
supervisor advance.
- If it is not clear enough, ask the blocking questions in your prose. The \
supervisor will end the turn and the user's next reply will re-enter scoping \
with the saved frame.
"""

scoping_agent: Agent[AgentDeps, str] = Agent(
    "openai:gpt-4.1-mini",
    output_type=str,
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
def _pinned_problem_frame(ctx: RunContext[AgentDeps]) -> str | None:
    return pinned_problem_frame(ctx)


@scoping_agent.instructions
def _pinned_graph_state(ctx: RunContext[AgentDeps]) -> str | None:
    return pinned_graph_state(ctx)


@scoping_agent.instructions
def _pinned_user_memories(ctx: RunContext[AgentDeps]) -> str | None:
    return pinned_user_memories(ctx)


SCOPING_USAGE_LIMITS = UsageLimits(
    request_limit=25,
    total_tokens_limit=250_000,
)
