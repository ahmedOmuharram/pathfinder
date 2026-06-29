from __future__ import annotations

from pydantic_ai.tools import RunContext

from pathfinder.ai.agents.param_vocab_render import render_param_vocab
from pathfinder.ai.agents.state import SearchOverview
from pathfinder.ai.context.rendering import render_graph_state
from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.prompts.loader import load_system_prompt
from pathfinder.ai.scratchpad.rendering import render_scratchpad_for_phase
from pathfinder.persistence.repositories.scratchpad import ScratchpadRepository


def base_system_prompt(ctx: RunContext[AgentDeps]) -> str:
    return load_system_prompt(include_site_hints=True)


def pinned_frame_workspace(ctx: RunContext[AgentDeps]) -> str | None:
    spec = ctx.deps.agent_state.operational_spec_draft
    if not spec.criteria and not spec.dropped:
        return None
    lines = ["# FRAME workspace (in-progress spec)"]
    for c in spec.criteria:
        slots = [s.param_name for s in c.open_params]
        line = f"- [{c.id}] {c.text[:60]} -> {c.search_name or '(UNBOUND)'}"
        if slots:
            line += f" | open: {slots}"
        lines.append(line)
    if spec.dropped:
        lines.append("dropped: " + "; ".join(d.text for d in spec.dropped))
    lines.append(
        f"structure_set={spec.structure is not None} "
        f"ready_to_build={spec.ready_to_build}"
    )
    return "\n".join(lines)


def pinned_graph_state(ctx: RunContext[AgentDeps]) -> str | None:
    session = ctx.deps.strategy_session
    graph = session.get_graph(None)
    if not graph or not graph.steps:
        return None
    return render_graph_state(graph, session.sync_state)


def pinned_ledger(ctx: RunContext[AgentDeps]) -> str | None:
    """The Lead's investigation ledger (curated structured state) — what's
    framed, discovered, planned, built, verified. Read-only shared context so
    a sub-agent knows what's already resolved and doesn't redo or re-ask it."""
    summary = ctx.deps.ledger_summary
    if not summary.strip():
        return None
    return f"## Investigation ledger (read-only)\n{summary}"


def pinned_user_memories(ctx: RunContext[AgentDeps]) -> str | None:
    memories = ctx.deps.retrieved_memories
    if not memories:
        return None
    lines = ["## What you know about this user"]
    for m in memories:
        tags_str = f" [{', '.join(m.tags)}]" if m.tags else ""
        lines.append(f"- [{m.kind}] {m.name}{tags_str}: {m.summary}")
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


def pinned_discovered_searches(ctx: RunContext[AgentDeps]) -> str | None:
    """Render the discovery gate's registered searches.

    Discovery commits searches into ``agent_state.discovered_searches`` as
    it inspects them. Planning + execution + verification all need to know
    what's available without re-reading the discovery agent's tool trace.
    Includes vocabulary snapshots captured by ``get_parameter_options`` so
    planning can copy values verbatim instead of guessing.
    """
    searches = ctx.deps.agent_state.discovered_searches
    if not searches:
        return None
    lines = ["## Discovered searches", ""]
    for name in sorted(searches):
        lines.extend(_render_search(name, searches[name]))
    return "\n".join(lines)


def _render_search(name: str, ov: SearchOverview) -> list[str]:
    header_bits = [f"`{name}`", f"({ov.record_type})"]
    if ov.selection_status != "candidate":
        header_bits.append(f"[{ov.selection_status}]")
    if ov.confidence > 0:
        header_bits.append(f"conf={ov.confidence:.2f}")
    out = [f"- {' '.join(header_bits)} — {ov.display_name}"]
    if ov.rationale:
        out.append(f"    why: {ov.rationale}")
    if ov.selection_reason:
        out.append(f"    decision: {ov.selection_reason}")
    if ov.selection_status == "rejected":
        return out
    if ov.required_params:
        out.append(f"    required params: {', '.join(ov.required_params)}")
    if ov.param_hints:
        hint_str = ", ".join(f"{k}={v}" for k, v in sorted(ov.param_hints.items()))
        out.append(f"    hints: {hint_str}")
    if ov.param_vocab:
        out.append("    param_vocab (copy values verbatim):")
        for pname in sorted(ov.param_vocab):
            out.extend(render_param_vocab(pname, ov.param_vocab[pname], indent=6))
    return out
