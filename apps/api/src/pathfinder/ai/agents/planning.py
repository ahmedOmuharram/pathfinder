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

from pathfinder.ai.agents._instructions import (
    base_system_prompt,
    mentioned_context,
    pinned_context_summary,
    pinned_graph_state,
    pinned_problem_frame,
)
from pathfinder.ai.agents._phase_decisions import PlanningDecision
from pathfinder.ai.capabilities.resilience import ToolResilience
from pathfinder.ai.capabilities.security import SecurityGuardrail
from pathfinder.ai.orchestration.deps import AgentDeps
from pathfinder.ai.tools.toolsets.planning import build_toolset
from pathfinder.domain.strategy.plan import PlanStatus, StepStatus

# ---------------------------------------------------------------------------
# Static instructions
# ---------------------------------------------------------------------------

_PLANNING_INSTRUCTIONS = """\
You are the Planning Agent for PathFinder. You receive discovery findings \
about available WDK searches and parameters, and your job is to create a \
precise execution plan.

The scoping phase may provide a pinned "Current Problem Frame". Use it as \
the authoritative problem statement, including assumptions and success \
criteria, while creating the plan.

## Your Responsibilities

1. **Analyze discovery findings**: Review the searches, parameters, and \
literature context discovered in the previous phase.

2. **Create a plan**: Use `create_plan` to define the sequence of strategy \
operations (leaf steps, combinations, transforms) needed to answer the \
user's question.

3. **Specify parameters**: For each step in the plan, specify exact \
parameter values based on discovery findings. Use `resolve_gene_ids_to_records` \
if the plan requires gene ID lookups.

4. **Submit for execution**: Once the plan is complete and reviewed, use \
`submit_plan` to hand it off to the execution agent. The submit_plan tool \
returns the canonical plan id — use that value as the `plan_id` field of \
your final PlanningDecision.

## Final Output

When the plan is ready, produce a `PlanningDecision` as your final output. \
Do NOT call any `finish_*` tool; those tools no longer exist.

Choose `next_action` based on what you did:
  - `advance_to_execution`: a plan has been submitted successfully; include \
its id in `plan_id`.
  - `request_revision`: the user needs to decide something before the plan \
can be submitted; reuse the draft plan id you last used, or "" if none was \
drafted.
  - `abort`: the task is not feasible with the available discovery findings; \
`plan_id` should be "" and `reason` should explain why.

Populate every field:
  - `plan_id`: canonical plan id returned by `submit_plan`, or "" for \
abort / request_revision with no draft.
  - `reason`: one-to-two sentence justification for `next_action`.

## Guidelines

- Plans must be concrete: every step specifies searchName, operator, and \
parameter values. No placeholders or "TBD" values.
- Respect parameter dependencies: if param B depends on param A, the plan \
must set A before B (the execution agent handles refresh).
- Use `update_plan` to refine the plan if the user requests changes.
- Use `set_conversation_title` to give the conversation a descriptive name.
- Use `get_strategy` to check the current graph state if editing an \
existing strategy.
- `present_decision` is non-blocking. Do not rely on it to stop the pipeline.
- Do NOT execute strategy operations — that is the execution agent's job.
- Do NOT explore the catalog — that was the discovery agent's job. Use \
the findings you received.
"""

# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

planning_agent: Agent[AgentDeps, PlanningDecision] = Agent(
    "openai:gpt-4.1-mini",
    output_type=PlanningDecision,
    deps_type=AgentDeps,
    instructions=_PLANNING_INSTRUCTIONS,
    toolsets=[build_toolset()],
    capabilities=[ToolResilience(), Thinking(effort="high"), SecurityGuardrail()],
    retries=3,
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
def _pinned_problem_frame(ctx: RunContext[AgentDeps]) -> str | None:
    return pinned_problem_frame(ctx)


@planning_agent.instructions
def _pinned_graph_state(ctx: RunContext[AgentDeps]) -> str | None:
    return pinned_graph_state(ctx)


@planning_agent.instructions
def _mentioned_context(ctx: RunContext[AgentDeps]) -> str | None:
    return mentioned_context(ctx)


@planning_agent.instructions
def _replan_context(ctx: RunContext[AgentDeps]) -> str | None:
    """Inject failure context when re-entering planning after a failed execution."""
    plan = ctx.deps.agent_state.active_plan
    if plan is None or plan.status != PlanStatus.FAILED:
        return None

    failed = [s for s in plan.steps if s.status == StepStatus.FAILED]
    if not failed:
        return None

    lines = [
        "## Replanning Required",
        "",
        "The previous execution plan failed. Create a NEW plan with a "
        "different approach. Do NOT reuse the same searches or parameters "
        "that failed.",
        "",
        "### Failed Steps",
    ]
    for step in failed:
        reason = step.failure_reason or "unknown error"
        lines.append(
            f"- **{step.display_name}** ({step.step_type}, "
            f"search: `{step.search_name}`): {reason}"
        )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Default usage limits
# ---------------------------------------------------------------------------

PLANNING_USAGE_LIMITS = UsageLimits(
    request_limit=200,
    total_tokens_limit=500_000,
)
