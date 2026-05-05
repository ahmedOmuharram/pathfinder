from __future__ import annotations

from pydantic_ai import Agent, DeferredToolRequests
from pydantic_ai.capabilities import Hooks, Thinking
from pydantic_ai.tools import RunContext

from pathfinder.ai.agents._history_processor import (
    PHASE_HISTORY_PROCESSORS,
)
from pathfinder.ai.agents._instructions import (
    base_system_prompt,
    pinned_active_plan,
    pinned_discovered_searches,
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
from pathfinder.ai.tools.toolsets.planning import build_toolset
from pathfinder.domain.strategy.plan import PlanStatus, StepStatus

_planning_hooks: Hooks[AgentDeps] = Hooks(tool_execute=repetition_guard_hook)

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
user's question. Call ``create_plan`` ONCE. If the pinned Active Plan \
block already describes a plan, DO NOT call ``create_plan`` again — use \
``update_plan`` to modify it or call ``submit_plan`` to re-present.

3. **Specify parameters**: For each step in the plan, specify exact \
parameter values based on discovery findings. Use `resolve_gene_ids_to_records` \
if the plan requires gene ID lookups.

4. **Submit for approval**: Once the plan is complete, call `submit_plan` \
ONCE. ``submit_plan`` is an approval gate: it does NOT execute \
immediately. The system halts the turn and asks the user to approve, \
deny, or request changes. On their reply:

   - **Approved** — ``submit_plan`` executes for real, returns the \
     approved plan, and you end with \
     ``PhaseOutcome(disposition=handoff, handoff_to=execution)``.
   - **Denied / changes requested** — ``submit_plan`` returns a denial \
     message describing what the user wants. Call ``update_plan`` to \
     apply the change, then ``submit_plan`` again. End with \
     ``disposition=awaiting_user`` for the next approval round.

## Output

End your turn with concise prose summarizing the plan and its rationale. A \
supervisor reads your prose and routes the pipeline — it may send you back \
to discovery if a gap emerges, continue to execution, or end the turn to \
wait for the user.

NEVER skip the prose. A reply that is only tool calls with no visible text \
is a failure — the user sees a blank assistant message.

## Guidelines

- Plans must be concrete: every step specifies searchName, operator, and \
parameter values. No placeholders or "TBD" values.
- Respect parameter dependencies: if param B depends on param A, the plan \
must set A before B (the execution agent handles refresh).
- Use `update_plan` to refine the plan if the user requests changes.
- Use `get_strategy` to check the current graph state if editing an \
existing strategy.
- `present_decision` is non-blocking.
- Do NOT execute strategy operations — that is the execution agent's job.
- Do NOT explore the catalog — that was the discovery agent's job. Use \
the findings you received.

## Output — the PhaseOutcome contract

Return exactly one ``PhaseOutcome``:

- ``prose`` (required, user-facing): a concise summary of the plan and its \
rationale. This IS the assistant message the user reads.
- ``reason`` (required, short): one sentence explaining your routing \
choice.
- ``disposition``: the system halts automatically on the ``submit_plan`` \
approval gate; on that path you don't author a disposition at all. If \
the user already approved and you've just finished running ``submit_plan`` \
for real, use ``handoff`` with ``handoff_to=execution``.
- ``handoff_to`` (optional): ``execution`` (or ``discovery`` if a gap \
emerged).
"""

planning_agent: Agent[AgentDeps, PhaseOutcome | DeferredToolRequests] = Agent(
    "openai:gpt-4.1-mini",
    output_type=[PhaseOutcome, DeferredToolRequests],
    deps_type=AgentDeps,
    instructions=_PLANNING_INSTRUCTIONS,
    toolsets=[build_toolset(), build_scratchpad_toolset()],
    capabilities=[
        ToolResilience(),
        _planning_hooks,
        Thinking(effort="high"),

    ],
    history_processors=PHASE_HISTORY_PROCESSORS,
    retries=3,
    description="Creates structured execution plans from discovery findings",
    name="planning",
    defer_model_check=True,
)


for _fn in (
    base_system_prompt,
    pinned_problem_frame,
    pinned_graph_state,
    pinned_active_plan,
    pinned_user_memories,
    pinned_scratchpad,
    pinned_last_phase_outcome,
    pinned_discovered_searches,
    pinned_supervisor_log,
):
    planning_agent.instructions(_fn)


@planning_agent.instructions
def _replan_context(ctx: RunContext[AgentDeps]) -> str | None:
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


