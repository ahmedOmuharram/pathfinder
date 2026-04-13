"""Discovery-phase agent — explores the WDK catalog and literature.

This agent handles the first phase of the PathFinder pipeline: understanding
what searches, parameters, and record types are available on the target
VEuPathDB site, and gathering relevant literature context.
"""

from __future__ import annotations

from pydantic_ai import Agent
from pydantic_ai.capabilities import Hooks, Thinking
from pydantic_ai.tools import RunContext
from pydantic_ai.usage import UsageLimits

from pathfinder.ai.agents._hooks import apply_discovery_hook
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
from pathfinder.ai.tools.toolsets.discovery import build_toolset
from pathfinder.domain.strategy.plan import PlanStatus, StepStatus

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

The scoping phase may provide a pinned "Current Problem Frame". Treat it as \
the authoritative interpretation of the user's goal and preserve its \
assumptions unless WDK evidence contradicts them.

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

6. **End the phase explicitly**: Call `finish_discovery` exactly once as your \
last tool call. Use `decision="ask_user"` only when a WDK-specific ambiguity \
would materially change the plan. Use `decision="continue_to_planning"` when \
the planner has enough information to build a concrete plan.

## Guidelines

- Be thorough: inspect ALL promising searches, not just the first match.
- Check parameter vocabularies — a search is only useful if its parameters \
can express the user's constraints.
- Record types matter: gene/transcript searches return different result sets.
- When multiple searches could work, note the trade-offs for the planner.
- Do NOT create or modify strategies — that is the execution agent's job.
- Do NOT create plans — that is the planning agent's job.
- If you ask the user a blocking question, call `finish_discovery` with \
`decision="ask_user"` and stop in that same turn.
- Summarize your findings clearly so the planning agent can act on them.
"""

# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

_discovery_hooks: Hooks[AgentDeps] = Hooks(after_tool_execute=apply_discovery_hook)

discovery_agent: Agent[AgentDeps, str] = Agent(
    "anthropic:claude-sonnet-4-5",
    deps_type=AgentDeps,
    instructions=_DISCOVERY_INSTRUCTIONS,
    toolsets=[build_toolset()],
    capabilities=[ToolResilience(), _discovery_hooks, Thinking(effort="medium"), SecurityGuardrail()],
    retries=3,
    description="Explores WDK catalog, searches, parameters, and literature",
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
def _pinned_problem_frame(ctx: RunContext[AgentDeps]) -> str | None:
    return pinned_problem_frame(ctx)


@discovery_agent.instructions
def _pinned_graph_state(ctx: RunContext[AgentDeps]) -> str | None:
    return pinned_graph_state(ctx)


@discovery_agent.instructions
def _mentioned_context(ctx: RunContext[AgentDeps]) -> str | None:
    return mentioned_context(ctx)


@discovery_agent.instructions
def _rediscovery_context(ctx: RunContext[AgentDeps]) -> str | None:
    """Inject failure context when re-entering discovery after a failed execution.

    Mirrors :func:`pathfinder.ai.agents.planning._replan_context`: when the
    FSM falls back from execution -> discovery (via the
    ``retry_discovery_from_execution`` transition) the previously chosen
    searches are suspect, so the agent must look for *different* ones instead
    of re-inspecting the same catalog entries.
    """
    plan = ctx.deps.agent_state.active_plan
    if plan is None or plan.status != PlanStatus.FAILED:
        return None

    failed = [s for s in plan.steps if s.status == StepStatus.FAILED]
    if not failed:
        return None

    lines = [
        "## Rediscovery Required",
        "",
        "The previous execution plan failed in a way that suggests the chosen "
        "searches are wrong for the user's biological question, not just the "
        "parameters. Re-open the catalog and look for DIFFERENT searches. Do "
        "NOT re-propose the same searches that failed.",
        "",
        "### Failed Steps (avoid these searches)",
    ]
    for step in failed:
        reason = step.failure_reason or "unknown error"
        lines.append(
            f"- **{step.display_name}** ({step.step_type}, "
            f"search: `{step.search_name}`): {reason}"
        )
    lines.extend(
        [
            "",
            "Explore alternative record types, search categories, or related "
            "queries that could answer the same question with a different "
            "data source.",
        ]
    )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Default usage limits
# ---------------------------------------------------------------------------

DISCOVERY_USAGE_LIMITS = UsageLimits(
    request_limit=50,
    total_tokens_limit=500_000,
)
