"""Pinned instructions that describe PathFinder's strategy work: the system
prompt, the in-progress spec, the live graph, the ledger and the searches
FRAME inspected."""

from __future__ import annotations

from pydantic_ai.tools import RunContext

from pathfinder.ai.agents.param_vocab_render import render_param_vocab
from pathfinder.ai.agents.state import SearchOverview
from pathfinder.ai.context.rendering import render_graph_state
from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.prompts.loader import load_system_prompt
from pathfinder.domain.parameters.value_codec import to_wire


def base_system_prompt(ctx: RunContext[AgentDeps]) -> str:
    return load_system_prompt(include_site_hints=True)


def pinned_frame_workspace(ctx: RunContext[AgentDeps]) -> str | None:
    spec = ctx.deps.agent_state.operational_spec_draft
    if not spec.criteria and not spec.dropped:
        return None
    lines = [
        "# FRAME workspace (in-progress spec)",
        "Values shown here are already bound and are preserved unless the "
        "request changes them.",
    ]
    for c in spec.criteria:
        slots = [s.param_name for s in c.open_params]
        saved = c.saved_strategy_ref
        bound_to = c.search_name or (saved.label if saved is not None else "(UNBOUND)")
        line = f"- [{c.id}] {c.text[:60]} -> {bound_to}"
        if slots:
            line += f" | open: {slots}"
        lines.append(line)
        lines.extend(
            f"    {name}={to_wire(value)}" for name, value in c.resolved_params.items()
        )
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


def pinned_discovered_searches(ctx: RunContext[AgentDeps]) -> str | None:
    """Render the searches FRAME has inspected so far.

    FRAME's catalog tools commit each search into
    ``agent_state.discovered_searches`` as they inspect it, and it is
    persisted on the graph state so later turns see it too. This is a cache
    of what the catalog returned, not the source of truth for the plan --
    that is the ``OperationalSpec``. Recovery and verification read it to
    know what is available without re-reading FRAME's tool trace. Includes
    vocabulary snapshots captured by ``get_parameter_options`` so values are
    copied verbatim instead of guessed.
    """
    searches = ctx.deps.agent_state.discovered_searches
    if not searches:
        return None
    lines = ["## Discovered searches", ""]
    for name in sorted(searches):
        lines.extend(_render_search(name, searches[name]))
    return "\n".join(lines)


def _render_search(name: str, ov: SearchOverview) -> list[str]:
    out = [f"- `{name}` ({ov.record_type}) — {ov.display_name}"]
    if ov.required_params:
        out.append(f"    required params: {', '.join(ov.required_params)}")
    if ov.param_vocab:
        out.append("    param_vocab (copy values verbatim):")
        for pname in sorted(ov.param_vocab):
            out.extend(render_param_vocab(pname, ov.param_vocab[pname], indent=6))
    return out
