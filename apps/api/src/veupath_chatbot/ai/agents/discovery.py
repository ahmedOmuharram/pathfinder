"""Discovery-phase agent — explores the WDK catalog and literature.

This agent handles the first phase of the PathFinder pipeline: understanding
what searches, parameters, and record types are available on the target
VEuPathDB site, and gathering relevant literature context.
"""

from __future__ import annotations

from pydantic_ai import Agent
from pydantic_ai.tools import RunContext
from pydantic_ai.usage import UsageLimits

from veupath_chatbot.ai.agents._hooks import executor_hooks
from veupath_chatbot.ai.agents._instructions import (
    base_system_prompt,
    mentioned_context,
    pinned_context_summary,
    pinned_graph_state,
)
from veupath_chatbot.ai.orchestration.deps import AgentDeps
from veupath_chatbot.ai.tools.toolsets.discovery import build_toolset

# ---------------------------------------------------------------------------
# Static instructions
# ---------------------------------------------------------------------------

_DISCOVERY_INSTRUCTIONS = """\
You are the Discovery Agent for PathFinder, a research accelerator for \
VEuPathDB pathogen databases. Your role is to explore the WDK catalog to \
find the right searches, parameters, and data sources for the user's \
biological question.

## Your Responsibilities

1. **Understand the question**: Parse the user's biological question into \
concrete data requirements (organism, gene properties, expression conditions, \
genomic features, etc.).

2. **Explore the catalog**: Use `get_record_types`, `search_for_searches`, \
`browse_search_categories`, and `list_searches` to find relevant WDK searches.

3. **Inspect searches**: Use `get_search_overview` to understand parameter \
requirements, then `get_parameter_options` and `get_parameter_dependencies` \
to understand vocabularies and dependent parameter chains.

4. **Gather literature context**: Use `literature_search` and `web_search` \
when the biological question requires domain knowledge you lack (gene names, \
pathway identifiers, organism-specific terminology).

5. **Check existing work**: Use `get_strategy` to inspect any strategy \
already in progress. Use `search_example_plans` to find similar solved \
problems.

## Guidelines

- Be thorough: inspect ALL promising searches, not just the first match.
- Check parameter vocabularies — a search is only useful if its parameters \
can express the user's constraints.
- Record types matter: gene/transcript searches return different result sets.
- When multiple searches could work, note the trade-offs for the planner.
- Do NOT create or modify strategies — that is the execution agent's job.
- Do NOT create plans — that is the planning agent's job.
- Summarize your findings clearly so the planning agent can act on them.
"""

# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

discovery_agent: Agent[AgentDeps, str] = Agent(
    "anthropic:claude-sonnet-4-5",
    deps_type=AgentDeps,
    instructions=_DISCOVERY_INSTRUCTIONS,
    toolsets=[build_toolset()],
    capabilities=[executor_hooks],
    name="discovery",
    defer_model_check=True,
)


@discovery_agent.instructions
def _base_system_prompt(ctx: RunContext[AgentDeps]) -> str:
    return base_system_prompt(ctx)


@discovery_agent.instructions
def _pinned_context_summary(ctx: RunContext[AgentDeps]) -> str | None:
    return pinned_context_summary(ctx)


@discovery_agent.instructions
def _pinned_graph_state(ctx: RunContext[AgentDeps]) -> str | None:
    return pinned_graph_state(ctx)


@discovery_agent.instructions
def _mentioned_context(ctx: RunContext[AgentDeps]) -> str | None:
    return mentioned_context(ctx)


# ---------------------------------------------------------------------------
# Default usage limits
# ---------------------------------------------------------------------------

DISCOVERY_USAGE_LIMITS = UsageLimits(
    request_limit=20,
    total_tokens_limit=50_000,
)
