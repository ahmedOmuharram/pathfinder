"""The Lead Agent's sub-agent dispatch tools.

The six tool wrappers the Lead invokes to run a phase sub-agent (plus the
``AgentDeps`` construction they share). The streaming/runner machinery they
call lives in ``sub_agent_tools``.
"""

from __future__ import annotations

from langgraph.config import get_stream_writer
from pydantic_ai import RunContext
from pydantic_ai.exceptions import ModelRetry

from pathfinder.ai.agents.state import AgentToolState
from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.graph.state import PipelineState, PlanSlotAnswer
from pathfinder.ai.lead.deltas import (
    DiscoveryDelta,
    ExecuteDelta,
    FrameDelta,
    PlanDelta,
    RecoveryDelta,
    VerificationDelta,
)
from pathfinder.ai.lead.derive import derive_ledger
from pathfinder.ai.lead.plan_reconcile import reconcile_plan_with_replacements
from pathfinder.ai.lead.sub_agent_tools import (
    LeadDeps,
    _apply_agent_state,
    _stream_sub_agent,
)
from pathfinder.ai.tools.standalone._stream_parts import graph_snapshot_chunk
from pathfinder.domain.strategy.build_outcome import BuildOutcome
from pathfinder.services.strategies.auto_import import (
    import_gene_set_for_conversation,
)
from pathfinder.services.strategies.plan_to_spec import build_step_tree_from_plan
from pathfinder.services.strategies.spec_build import build_strategy_from_spec


def _slot_answers(state: PipelineState) -> list[PlanSlotAnswer]:
    pending = state.pending_approval
    if pending is None:
        return []
    return list(state.plan_slot_answers.get(pending.tool_call_id, []))


def _agent_deps(deps: LeadDeps) -> AgentDeps:
    state = deps.state
    runtime = deps.runtime
    return AgentDeps(
        site_id=runtime.site_id,
        user_id=runtime.user_id,
        strategy_session=runtime.strategy_session,
        web_search_service=runtime.web_search_service,
        literature_search_service=runtime.literature_search_service,
        agent_state=AgentToolState(
            discovered_searches=dict(state.discovered_searches),
            active_plan=state.active_plan,
        ),
        problem_frame=state.problem_frame,
        ledger_summary=derive_ledger(state, deps.intent).render_summary(),
        experiment_id=runtime.experiment_id,
        cancel_event=runtime.cancel_event,
        memory_store=runtime.memory_store,
        retrieved_memories=deps.retrieved_memories,
        conversation_id=state.conversation_id,
        db_session_factory=runtime.db_session_factory,
        plan_slot_answers=_slot_answers(state),
    )


def _parent_tool_call_id(ctx: RunContext[LeadDeps]) -> str:
    """The Lead's tool_call_id for the active sub-agent dispatch.
    Always present when invoked through the Lead's toolset; defensively
    returns an empty string if missing so we never crash on telemetry."""
    return ctx.tool_call_id or ""


async def scope_problem(
    ctx: RunContext[LeadDeps],
    reason: str,
) -> FrameDelta:
    """Run the scoping sub-agent to frame the user's problem.

    Use when the Ledger reports ``frame.needed`` is True. The sub-agent
    returns a ``FrameDelta`` containing the saved ``ProblemFrame`` and
    any blocking questions that the Lead must surface to the user.
    """
    deps = ctx.deps
    work_order = (
        f"Scoping work order: {reason}\n"
        f"User's latest message: {deps.state.user_prompt}\n"
        "Frame the biological problem. Return a FrameDelta."
    )
    agent_deps = _agent_deps(deps)
    delta = await _stream_sub_agent(
        role="scoping",
        work_order=work_order,
        agent_deps=agent_deps,
        parent_tool_call_id=_parent_tool_call_id(ctx),
        expected_output_type=FrameDelta,
        deps=deps,
    )
    _apply_agent_state(deps, agent_deps)
    if delta is None:
        msg = "Scoping sub-agent did not return a FrameDelta."
        raise RuntimeError(msg)
    deps.state.problem_frame = delta.frame
    # Consumed: scoping has folded the reply in — don't re-scope again this turn.
    deps.state.rescope_requested = False
    return delta


def _discovery_work_order(
    reason: str,
    intent_summary: str,
    hints: str,
    *,
    keep_prior_selections: bool,
) -> str:
    parts = [f"Discovery work order: {reason}", f"Intent: {intent_summary}"]
    if keep_prior_selections:
        parts.append(
            "TARGETED RE-DISCOVERY: this is an incremental pass, not a fresh "
            "start. KEEP every currently-`selected` search exactly as-is — do "
            "NOT re-evaluate or reject them. Find ONLY the search(es) named in "
            "the Intent/Hints above. If you are REPLACING an existing search, "
            "reject the old one explicitly and select the replacement.",
        )
    if hints:
        parts.append(f"Hints: {hints}")
    parts.append("Return a DiscoveryDelta.")
    return "\n".join(parts)


async def discover_searches(
    ctx: RunContext[LeadDeps],
    reason: str,
    intent_summary: str,
    hints: str = "",
    *,
    keep_prior_selections: bool = False,
    supersedes: str = "",
) -> DiscoveryDelta:
    """Run the discovery sub-agent to find WDK searches.

    ``hints`` carries Lead-derived guidance (e.g. "vocab gap: prior
    selection covers gametocyte but not asexual blood stages — find a
    search whose vocab spans both"). Set ``keep_prior_selections=True``
    when re-dispatching after a plan denial that needs a different/missing
    search basis: the sub-agent then keeps all selected searches and finds
    ONLY what ``intent_summary``/``hints`` name. When the denial REPLACES a
    search already in the plan, also pass ``supersedes=<that search name>``:
    once discovery finds the replacement, the plan leaf is swapped to it
    automatically (no hand-editing). The sub-agent commits selections via
    ``update_search_decision``; we mirror those onto state.
    """
    deps = ctx.deps
    work_order = _discovery_work_order(
        reason=reason,
        intent_summary=intent_summary,
        hints=hints,
        keep_prior_selections=keep_prior_selections,
    )
    agent_deps = _agent_deps(deps)
    delta = await _stream_sub_agent(
        role="discovery",
        work_order=work_order,
        agent_deps=agent_deps,
        parent_tool_call_id=_parent_tool_call_id(ctx),
        expected_output_type=DiscoveryDelta,
        deps=deps,
    )
    _apply_agent_state(deps, agent_deps)
    if delta is None:
        msg = "Discovery sub-agent did not return a DiscoveryDelta."
        raise RuntimeError(msg)
    _reconcile_active_plan(deps, supersedes=supersedes or None)
    return delta


def _reconcile_active_plan(deps: LeadDeps, *, supersedes: str | None) -> None:
    """Apply discovery's replacements to the active plan deterministically
    (swap the superseded leaf), so the Lead never hand-edits the plan for a
    search swap. No-op when there's no plan or no replacement. *supersedes*
    is the Lead's denial classification (the plan search being replaced).
    Inference always runs: a reject-old + select-new pattern maps 1:1 even
    when the model emits no explicit link or flag — the reliable signal that
    a weak model actually produces."""
    plan = deps.state.active_plan
    if plan is None:
        return
    result = reconcile_plan_with_replacements(
        plan,
        deps.state.discovered_searches,
        infer_replacements=True,
        supersedes=supersedes,
    )
    if not result.changes:
        return
    deps.state.active_plan = result.plan
    agent_deps = _agent_deps(deps)
    graph = agent_deps.strategy_session.get_graph(None)
    if graph is not None:
        get_stream_writer()(
            {
                "chunk": graph_snapshot_chunk(
                    agent_deps.strategy_session, graph
                ).model_dump(by_alias=True, mode="json", exclude_none=True),
            },
        )


async def build_plan(
    ctx: RunContext[LeadDeps],
    reason: str,
) -> PlanDelta:
    """Run the planning sub-agent to construct a strategy plan.

    The sub-agent does NOT submit the plan — it only authors it. The
    Lead is responsible for surfacing the plan to the user via its own
    ``submit_plan_for_approval`` deferred-tool.
    """
    deps = ctx.deps
    if not any(
        ov.selection_status == "selected"
        for ov in deps.state.discovered_searches.values()
    ):
        msg = (
            "Discovery has committed zero searches — planning would have no "
            "real WDK searches to build from and would invent search names. "
            "Call discover_searches first; only call build_plan once discovery "
            "has selected at least one search."
        )
        raise ModelRetry(msg)
    work_order = (
        f"Planning work order: {reason}\n"
        "Construct a complete StrategyPlan from the discovered searches.\n"
        "Return a PlanDelta."
    )
    agent_deps = _agent_deps(deps)
    delta = await _stream_sub_agent(
        role="planning",
        work_order=work_order,
        agent_deps=agent_deps,
        parent_tool_call_id=_parent_tool_call_id(ctx),
        expected_output_type=PlanDelta,
        deps=deps,
    )
    _apply_agent_state(deps, agent_deps)
    if agent_deps.agent_state.active_plan is None:
        msg = "Planning sub-agent returned no plan."
        raise RuntimeError(msg)
    if delta is not None:
        return delta
    return PlanDelta()


async def execute_plan(ctx: RunContext[LeadDeps]) -> ExecuteDelta:
    """Materialize the APPROVED plan declaratively (no LLM).

    Builds a ``StrategyStepNode`` tree from the plan and pushes it via
    ``build_strategy_from_spec``. The Lead inspects the returned outcome
    via ``ledger.build`` to decide whether to call ``recover_failed_steps``
    or ``verify_strategy``.
    """
    deps = ctx.deps
    plan = deps.state.active_plan
    if plan is None:
        msg = "No active plan to execute. Build a plan first."
        raise RuntimeError(msg)
    root = build_step_tree_from_plan(plan)
    agent_deps = _agent_deps(deps)
    outcome: BuildOutcome = await build_strategy_from_spec(
        deps=agent_deps.to_strategy_context(),
        root=root,
        name=plan.title or None,
    )
    deps.state.last_build_outcome = outcome
    graph = agent_deps.strategy_session.get_graph(None)
    if graph is not None:
        get_stream_writer()(
            {
                "chunk": graph_snapshot_chunk(
                    agent_deps.strategy_session, graph
                ).model_dump(by_alias=True, mode="json", exclude_none=True),
            },
        )
    if (
        outcome.wdk_strategy_id is not None
        and agent_deps.user_id is not None
        and agent_deps.conversation_id is not None
    ):
        await import_gene_set_for_conversation(
            conversation_id=agent_deps.conversation_id,
            site_id=agent_deps.site_id,
            user_id=agent_deps.user_id,
        )
    return ExecuteDelta(outcome=outcome)


async def recover_failed_steps(
    ctx: RunContext[LeadDeps],
    reason: str,
) -> RecoveryDelta:
    """Run the LLM execution-recovery sub-agent on a failed build.

    Only valid when ``ledger.build.needs_recovery`` is True and the
    failure shape is amenable to targeted edits (param replan, partial
    build). For ``search_replan`` the Lead should call
    ``discover_searches`` instead.
    """
    deps = ctx.deps
    outcome = deps.state.last_build_outcome
    if outcome is None:
        msg = "No build outcome to recover from."
        raise RuntimeError(msg)
    work_order_parts = [
        f"Recovery work order: {reason}",
        f"Failed steps: {len(outcome.failed_steps)}",
        f"Skipped: {len(outcome.skipped_step_ids)}",
        f"Zero-result: {len(outcome.zero_step_ids)}",
        "Edit the affected steps via update_leaf_params / replace_subtree.",
        "Return a RecoveryDelta with actions_taken and final_outcome.",
    ]
    work_order = "\n".join(work_order_parts)
    agent_deps = _agent_deps(deps)
    streamed = await _stream_sub_agent(
        role="execution",
        work_order=work_order,
        agent_deps=agent_deps,
        parent_tool_call_id=_parent_tool_call_id(ctx),
        expected_output_type=RecoveryDelta,
        deps=deps,
    )
    _apply_agent_state(deps, agent_deps)
    delta = (
        streamed
        if streamed is not None
        else RecoveryDelta(
            final_outcome=outcome,
        )
    )
    deps.state.last_build_outcome = delta.final_outcome
    return delta


async def verify_strategy(
    ctx: RunContext[LeadDeps],
    reason: str,
) -> VerificationDelta:
    """Run the verification sub-agent on the built strategy."""
    deps = ctx.deps
    work_order = (
        f"Verification work order: {reason}\n"
        "Inspect the built strategy. Return a VerificationDelta."
    )
    agent_deps = _agent_deps(deps)
    delta = await _stream_sub_agent(
        role="verification",
        work_order=work_order,
        agent_deps=agent_deps,
        parent_tool_call_id=_parent_tool_call_id(ctx),
        expected_output_type=VerificationDelta,
        deps=deps,
    )
    _apply_agent_state(deps, agent_deps)
    if delta is None:
        msg = "Verification sub-agent did not return a VerificationDelta."
        raise TypeError(msg)
    deps.state.verification_digest = delta.digest
    return delta
