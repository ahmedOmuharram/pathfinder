"""What the Lead reads before it acts.

One render per pinned instruction: the message it answers, the intent it
classified, the spec it frames against, the ledger it decides from, and what
moved on the thread since it last answered.
"""

from __future__ import annotations

from pydantic_ai import RunContext

from pathfinder.ai.lead.derive import derive_ledger
from pathfinder.ai.lead.sub_agent_tools import LeadDeps

__all__ = [
    "pinned_ledger_summary",
    "pinned_operational_spec",
    "pinned_turn_briefing",
    "pinned_user_intent",
    "pinned_user_prompt",
]


def pinned_ledger_summary(ctx: RunContext[LeadDeps]) -> str:
    """Builds the compact ledger summary. It is derived on each render."""
    ledger = derive_ledger(
        ctx.deps.state,
        ctx.deps.intent,
        phase_stop=ctx.deps.last_phase_stop,
    )
    return ledger.render_summary()


def pinned_operational_spec(ctx: RunContext[LeadDeps]) -> str | None:
    """Renders the operational spec, which the Lead reads to decide build readiness."""
    spec = ctx.deps.state.domain.operational_spec
    if spec is None:
        return "## Operational Spec\nNot framed yet. Call ``frame_problem``."
    lines = [
        "## Operational Spec",
        f"- goal: {spec.interpreted_goal or spec.goal}",
        f"- ready_to_build: {spec.ready_to_build}",
    ]
    for c in spec.criteria:
        slots = [s.param_name for s in c.open_params]
        line = f"  - [{c.id}] {c.text[:60]} -> {c.search_name or '(UNBOUND)'}"
        if slots:
            line += f" | open: {slots}"
        lines.append(line)
    if spec.dropped:
        lines.append("  dropped: " + "; ".join(d.text for d in spec.dropped))
    return "\n".join(lines)


def pinned_user_intent(ctx: RunContext[LeadDeps]) -> str | None:
    intent = ctx.deps.intent
    if intent is None:
        return (
            "## User Intent\nNot classified yet. Call ``classify_user_intent`` first."
        )
    lines = [
        "## User Intent",
        f"- classification: {intent.classification.value}",
        f"- inferred goal: {intent.inferred_goal}",
    ]
    if intent.is_differential and intent.differential_sides:
        lines.append(f"- differential sides: {intent.differential_sides}")
    if intent.referenced_step_ids:
        lines.append(f"- referenced steps: {intent.referenced_step_ids}")
    if intent.referenced_strategy_ids:
        lines.append(
            f"- referenced strategies: {intent.referenced_strategy_ids}",
        )
    return "\n".join(lines)


def pinned_turn_briefing(ctx: RunContext[LeadDeps]) -> str | None:
    """What moved on the thread since the Lead last answered, or nothing."""
    return ctx.deps.state.domain.turn_briefing or None


def pinned_user_prompt(ctx: RunContext[LeadDeps]) -> str | None:
    prompt = ctx.deps.state.user_prompt
    if not prompt:
        return None
    return f"## User's latest message\n{prompt}"
