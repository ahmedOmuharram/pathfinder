from __future__ import annotations

from pydantic_ai.tools import RunContext

from pathfinder.ai.context.rendering import render_graph_state
from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.graph.state import PhaseDisposition
from pathfinder.ai.prompts.loader import load_system_prompt
from pathfinder.ai.scratchpad.rendering import render_scratchpad_for_phase
from pathfinder.ai.scratchpad.repository import ScratchpadRepository
from pathfinder.domain.strategy.plan import PlanStatus


def base_system_prompt(ctx: RunContext[AgentDeps]) -> str:
    return load_system_prompt(include_site_hints=True)


def _bullet_list(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items if item]


def pinned_problem_frame(ctx: RunContext[AgentDeps]) -> str | None:
    frame = ctx.deps.problem_frame
    if frame is None:
        return None

    lines = [
        "## Current Problem Frame",
        f"- User goal: {frame.user_goal}",
        f"- Interpreted goal: {frame.interpreted_goal}",
        f"- Ready for WDK discovery: {frame.ready_for_wdk_discovery}",
        f"- Confidence: {frame.confidence:.2f}",
    ]
    if frame.organism_scope:
        lines.append(f"- Organism scope: {frame.organism_scope}")
    if frame.record_type:
        lines.append(f"- Target record type: {frame.record_type}")

    sections = [
        ("Biological entities", frame.biological_entities),
        ("Inclusion criteria", frame.inclusion_criteria),
        ("Exclusion criteria", frame.exclusion_criteria),
        ("Likely data sources", frame.likely_data_sources),
        ("Success criteria", frame.success_criteria),
        ("Assumptions", frame.assumptions),
    ]
    for heading, items in sections:
        rendered = _bullet_list(items)
        if rendered:
            lines.extend(["", f"### {heading}", *rendered])

    if frame.blocking_questions:
        lines.extend(["", "### Blocking Questions"])
        lines.extend(f"- {q.question}" for q in frame.blocking_questions)
    if frame.optional_questions:
        lines.extend(["", "### Optional Clarifications (non-blocking)"])
        lines.extend(f"- {q.question}" for q in frame.optional_questions)

    return "\n".join(lines)


def pinned_graph_state(ctx: RunContext[AgentDeps]) -> str | None:
    session = ctx.deps.strategy_session
    graph = session.get_graph(None)
    if not graph or not graph.steps:
        return None
    return render_graph_state(graph, session.sync_state)


def pinned_user_memories(ctx: RunContext[AgentDeps]) -> str | None:
    memories = ctx.deps.retrieved_memories
    if not memories:
        return None
    lines = ["## What you know about this user"]
    for m in memories:
        tags_str = f" [{', '.join(m.tags)}]" if m.tags else ""
        lines.append(f"- [{m.kind}] {m.name}{tags_str}: {m.summary}")
    return "\n".join(lines)


def pinned_active_plan(ctx: RunContext[AgentDeps]) -> str | None:
    """Show the planner an already-authored plan so it doesn't re-author.

    ``FAILED`` status is intentionally omitted: the planner's own
    ``_replan_context`` handles that case with targeted guidance.
    """
    plan = ctx.deps.agent_state.active_plan
    if plan is None or plan.status == PlanStatus.FAILED:
        return None
    lines = [
        "## Active Plan — already authored",
        f"- id: {plan.id}",
        f"- title: {plan.title}",
        f"- status: {plan.status.value}",
        f"- step_count: {len(plan.steps)}",
        "",
        "DO NOT call `create_plan` again. Use `get_plan` to inspect, "
        "`update_plan` to modify, or `submit_plan` to (re)present for "
        "approval.",
    ]
    if plan.status == PlanStatus.APPROVED:
        lines.extend(
            [
                "",
                "**The user has already approved this plan.** DO NOT call "
                "`submit_plan` again. DO NOT ask the user to approve. "
                "Emit `PhaseOutcome(disposition=handoff, "
                "handoff_to=\"execution\")` with short prose confirming "
                "the plan is approved and execution is starting.",
            ],
        )
    return "\n".join(lines)


async def pinned_scratchpad(ctx: RunContext[AgentDeps]) -> str | None:
    """Render the conversation's scratchpad index for the phase agent."""
    if ctx.deps.db_session_factory is None or ctx.deps.conversation_id is None:
        return None
    async with ctx.deps.db_session_factory() as session:
        repo = ScratchpadRepository(session)
        notes, total_count, _ = await repo.list_for_index_with_totals(
            conversation_id=ctx.deps.conversation_id,
        )
    return render_scratchpad_for_phase(notes, total_count=total_count)


_DISPOSITION_LABEL: dict[PhaseDisposition, str] = {
    PhaseDisposition.AWAITING_USER: "awaiting user reply",
    PhaseDisposition.HANDOFF: "handed off",
    PhaseDisposition.DONE: "ended turn",
}


def pinned_last_phase_outcome(ctx: RunContext[AgentDeps]) -> str | None:
    """Render the previous phase's structured outcome.

    Replaces the role that ``message_history`` used to play across phases:
    instead of the next agent re-reading the prior phase's tool trace, it
    sees a compact summary of *what the previous phase concluded* — its
    disposition, routing target, user-facing prose, and routing rationale.
    """
    outcome = ctx.deps.last_phase_outcome
    if outcome is None:
        return None
    source_phase = ctx.deps.last_phase_name or "previous phase"
    disposition_label = _DISPOSITION_LABEL.get(
        outcome.disposition, outcome.disposition.value,
    )
    lines = [
        f"## Previous phase ({source_phase}) outcome",
        f"- Disposition: {disposition_label}",
    ]
    if outcome.handoff_to is not None:
        lines.append(f"- Handed off to: {outcome.handoff_to}")
    lines.extend([
        f"- Reason: {outcome.reason}",
        "",
        "### What the previous phase reported",
        outcome.prose,
    ])
    if outcome.note_refs:
        lines.extend([
            "",
            "### Supporting scratchpad notes",
            *(f"- {ref}" for ref in outcome.note_refs),
        ])
    return "\n".join(lines)


def pinned_discovered_searches(ctx: RunContext[AgentDeps]) -> str | None:
    """Render the discovery gate's registered searches.

    Discovery commits searches into ``agent_state.discovered_searches`` as
    it inspects them. Planning + execution + verification all need to know
    what's available without re-reading the discovery agent's tool trace.
    """
    searches = ctx.deps.agent_state.discovered_searches
    if not searches:
        return None
    lines = ["## Discovered searches", ""]
    for name in sorted(searches):
        ov = searches[name]
        header_bits = [f"`{name}`", f"({ov.record_type})"]
        if ov.selection_status != "candidate":
            header_bits.append(f"[{ov.selection_status}]")
        if ov.confidence > 0:
            header_bits.append(f"conf={ov.confidence:.2f}")
        lines.append(f"- {' '.join(header_bits)} — {ov.display_name}")
        if ov.rationale:
            lines.append(f"    why: {ov.rationale}")
        if ov.selection_reason:
            lines.append(f"    decision: {ov.selection_reason}")
        if ov.required_params:
            lines.append(
                f"    required params: {', '.join(ov.required_params)}",
            )
        if ov.param_hints:
            hint_str = ", ".join(
                f"{k}={v}" for k, v in sorted(ov.param_hints.items())
            )
            lines.append(f"    hints: {hint_str}")
    return "\n".join(lines)
