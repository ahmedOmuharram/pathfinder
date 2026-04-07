"""Planning-phase agent — builds structured execution plans.

This agent receives discovery findings (via message_history from the
discovery phase) and produces a concrete, step-by-step plan for the
execution agent to follow.
"""

from __future__ import annotations

from pydantic_ai import Agent
from pydantic_ai.capabilities import Thinking
from pydantic_ai.tools import RunContext
from pydantic_ai.usage import UsageLimits

from veupath_chatbot.ai.agents._instructions import (
    base_system_prompt,
    mentioned_context,
    pinned_context_summary,
    pinned_graph_state,
)
from veupath_chatbot.ai.capabilities.security import SecurityGuardrail
from veupath_chatbot.ai.orchestration.deps import AgentDeps
from veupath_chatbot.ai.tools.toolsets.planning import build_toolset

# ---------------------------------------------------------------------------
# Static instructions
# ---------------------------------------------------------------------------

_PLANNING_INSTRUCTIONS = """\
You are the Planning Agent for PathFinder. You receive discovery findings \
about available WDK searches and parameters, and your job is to create a \
precise execution plan.

## Your Responsibilities

1. **Analyze discovery findings**: Review the searches, parameters, and \
literature context discovered in the previous phase.

2. **Create a plan**: Use `create_plan` to define the sequence of strategy \
operations (leaf steps, combinations, transforms) needed to answer the \
user's question.

3. **Specify parameters**: For each step in the plan, specify exact \
parameter values based on discovery findings. Use `resolve_gene_ids_to_records` \
if the plan requires gene ID lookups.

4. **Handle ambiguity**: When the discovery findings leave multiple valid \
approaches, use `present_decision` to ask the user which path to take. \
Do NOT guess — let the user decide.

5. **Submit for execution**: Once the plan is complete and reviewed, use \
`submit_plan` to hand it off to the execution agent.

## Guidelines

- Plans must be concrete: every step specifies searchName, operator, and \
parameter values. No placeholders or "TBD" values.
- Respect parameter dependencies: if param B depends on param A, the plan \
must set A before B (the execution agent handles refresh).
- Use `update_plan` to refine the plan if the user requests changes.
- Use `set_conversation_title` to give the conversation a descriptive name.
- Use `get_strategy` to check the current graph state if editing an \
existing strategy.
- Do NOT execute strategy operations — that is the execution agent's job.
- Do NOT explore the catalog — that was the discovery agent's job. Use \
the findings you received.
"""

# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

planning_agent: Agent[AgentDeps, str] = Agent(
    "anthropic:claude-sonnet-4-5",
    deps_type=AgentDeps,
    instructions=_PLANNING_INSTRUCTIONS,
    toolsets=[build_toolset()],
    capabilities=[Thinking(effort="high"), SecurityGuardrail()],
    description="Creates structured execution plans from discovery findings",
    name="planning",
    defer_model_check=True,
)


@planning_agent.instructions
def _base_system_prompt(ctx: RunContext[AgentDeps]) -> str:
    return base_system_prompt(ctx)


@planning_agent.instructions
def _pinned_context_summary(ctx: RunContext[AgentDeps]) -> str | None:
    return pinned_context_summary(ctx)


@planning_agent.instructions
def _pinned_graph_state(ctx: RunContext[AgentDeps]) -> str | None:
    return pinned_graph_state(ctx)


@planning_agent.instructions
def _mentioned_context(ctx: RunContext[AgentDeps]) -> str | None:
    return mentioned_context(ctx)


# ---------------------------------------------------------------------------
# Default usage limits
# ---------------------------------------------------------------------------

PLANNING_USAGE_LIMITS = UsageLimits(
    request_limit=15,
    total_tokens_limit=40_000,
)
