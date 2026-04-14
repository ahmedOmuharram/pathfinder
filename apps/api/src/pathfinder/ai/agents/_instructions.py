from __future__ import annotations

from pydantic_ai.tools import RunContext

from pathfinder.ai.context.rendering import render_graph_state
from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.prompts.loader import load_system_prompt


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

    return "\n".join(lines)


def pinned_graph_state(ctx: RunContext[AgentDeps]) -> str | None:
    session = ctx.deps.strategy_session
    graph = session.get_graph(None)
    if not graph or not graph.steps:
        return None
    return render_graph_state(graph, session.sync_state)
