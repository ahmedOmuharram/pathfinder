from __future__ import annotations

from pydantic_ai import Agent
from pydantic_ai.capabilities import Hooks, Thinking
from pydantic_ai.tools import RunContext

from pathfinder.ai.agents._history_processor import (
    PHASE_HISTORY_PROCESSORS,
)
from pathfinder.ai.agents._hooks import apply_discovery_hook
from pathfinder.ai.agents._instructions import (
    base_system_prompt,
    pinned_graph_state,
    pinned_last_phase_outcome,
    pinned_problem_frame,
    pinned_scratchpad,
    pinned_supervisor_log,
    pinned_user_memories,
)
from pathfinder.ai.capabilities.repetition_guard import repetition_guard_hook
from pathfinder.ai.capabilities.resilience import ToolResilience
from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.graph.state import PhaseOutcome
from pathfinder.ai.scratchpad.tools import build_scratchpad_toolset
from pathfinder.ai.tools.toolsets.discovery import build_toolset
from pathfinder.domain.strategy.plan import PlanStatus, StepStatus

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

After you've inspected a search and reached a verdict on it, call \
`update_search_decision` to commit that verdict — set ``selection_status`` \
to ``selected``, ``candidate``, or ``rejected``, with a ``rationale`` \
(why this search is biologically relevant), a ``selection_reason`` (why \
the status), a ``confidence`` (0..1), and any ``param_hints`` you settled \
on. Downstream phases read these decisions instead of replaying your tool \
trace, so be explicit. Recording rejected candidates is just as important \
as recording selected ones — it keeps planning from re-discovering the \
same dead ends.

4. **Gather literature context**: Use `literature_search` and `web_search` \
when the biological question requires domain knowledge you lack (gene names, \
pathway identifiers, organism-specific terminology).

5. **Check existing work**: Use `get_strategy` to inspect any strategy \
already in progress. Use `search_example_plans` to find similar solved \
problems.

## Output

End your turn with concise prose summarizing candidate searches, parameter \
trade-offs, and caveats so the planner and the user can see them. If \
catalog evidence reshapes the scoping frame, note the disagreement in your \
prose so the supervisor can route back to scoping. A supervisor reads your \
prose and decides whether to continue to planning, skip to execution, or \
end the turn to wait for the user.

NEVER skip the prose. A reply that is only tool calls with no visible text \
is a failure — the user sees a blank assistant message.

## Guidelines

- Be thorough: inspect ALL promising searches, not just the first match.
- Check parameter vocabularies — a search is only useful if its parameters \
can express the user's constraints.
- Record types matter: gene/transcript searches return different result sets.
- When multiple searches could work, note the trade-offs for the planner.
- Only the tools listed above are available in this phase. Strategy edits, \
plan authoring, and frame-setting belong to other phases — describe what \
the next phase should do; do NOT try to call tools you haven't been given.
- If you need the user to answer a blocking question, ask it in your prose \
and pick ``disposition="awaiting_user"``. The pipeline will halt.
- Summarize your findings clearly so the planning agent can act on them.

## Output — the PhaseOutcome contract

Return exactly one ``PhaseOutcome``:

- ``prose`` (required, user-facing): a concise summary of candidate \
searches, parameter trade-offs, and caveats. Written as the assistant \
message that appears in the chat thread.
- ``reason`` (required, short): one sentence explaining your routing \
choice.
- ``disposition``: ``awaiting_user`` when you asked the user to decide \
something the catalog can't resolve; ``handoff`` when you surfaced enough \
searches to move on.
- ``handoff_to`` (optional): hint ``planning`` or ``scoping`` (to revisit \
the frame).
"""

_discovery_hooks: Hooks[AgentDeps] = Hooks(
    after_tool_execute=apply_discovery_hook,
    tool_execute=repetition_guard_hook,
)

discovery_agent: Agent[AgentDeps, PhaseOutcome] = Agent(
    "openai:gpt-4.1-mini",
    output_type=PhaseOutcome,
    deps_type=AgentDeps,
    instructions=_DISCOVERY_INSTRUCTIONS,
    toolsets=[build_toolset(), build_scratchpad_toolset()],
    capabilities=[
        ToolResilience(),
        _discovery_hooks,
        Thinking(effort="medium"),

    ],
    history_processors=PHASE_HISTORY_PROCESSORS,
    retries=3,
    description="Explores WDK catalog, searches, parameters, and literature",
    name="discovery",
    defer_model_check=True,
)


for _fn in (
    base_system_prompt,
    pinned_problem_frame,
    pinned_graph_state,
    pinned_user_memories,
    pinned_scratchpad,
    pinned_last_phase_outcome,
    pinned_supervisor_log,
):
    discovery_agent.instructions(_fn)


@discovery_agent.instructions
def _rediscovery_context(ctx: RunContext[AgentDeps]) -> str | None:
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


