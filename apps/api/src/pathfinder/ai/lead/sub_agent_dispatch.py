"""The Lead Agent's sub-agent dispatch tools.

The tool wrappers the Lead invokes to run a phase sub-agent, and the phase
runs behind them that a resumed dispatch re-enters.
"""

from __future__ import annotations

from langgraph.config import get_stream_writer
from pydantic_ai import RunContext
from pydantic_ai.exceptions import ModelRetry

from pathfinder.ai.graph.runtime import AgentDeps, VerificationScope
from pathfinder.ai.graph.state import VerificationDigest
from pathfinder.ai.lead.deltas import (
    ExecuteDelta,
    FrameResult,
    RecoveryDelta,
    VerificationDelta,
)
from pathfinder.ai.lead.derive import derive_ledger
from pathfinder.ai.lead.dispatch_context import (
    agent_deps_for,
    defer_dispatch,
    dispatch_call_id,
    refuse_and_restore,
)
from pathfinder.ai.lead.dispatch_messages import (
    build_not_ready_message,
    build_would_replace_the_strategy,
    frame_bound_nothing_result,
    frame_claimed_more_than_it_bound,
    frame_result_from_draft,
    undeclared_spec_changes,
)
from pathfinder.ai.lead.ledger import (
    build_contradiction,
    digest_held_to_the_build,
)
from pathfinder.ai.lead.sub_agent_stream import (
    PhaseRun,
    SubAgentApprovalWait,
    SubAgentResume,
    stream_sub_agent,
)
from pathfinder.ai.lead.sub_agent_tools import (
    LeadDeps,
    apply_agent_state,
)
from pathfinder.ai.tools.standalone._stream_parts import graph_snapshot_chunk
from pathfinder.ai.tools.toolsets._dynamic import live_wdk_step_ids
from pathfinder.domain.strategy.build_outcome import BuildOutcome
from pathfinder.domain.strategy.operational_spec import (
    build_step_tree,
    renumber_criteria,
)
from pathfinder.domain.strategy.spec_diff import diff_specs
from pathfinder.platform.errors import AppError
from pathfinder.services.strategies.auto_import import (
    import_gene_set_for_conversation,
)
from pathfinder.services.strategies.spec_build import (
    build_strategy_from_spec,
    node_results,
)
from pathfinder.services.strategies.sync import sync_strategy_for_site
from pathfinder.services.strategies.sync_state import ensure_sync_state


def frame_work_order(reason: str, prompt: str) -> str:
    return (
        f"FRAME work order: {reason}\n"
        f"User's goal: {prompt}\n"
        "Operationalize into criteria, bind each to a real WDK search, resolve "
        "params, set the structure. Return a FrameResult."
    )


async def run_frame(
    *,
    deps: LeadDeps,
    parent_tool_call_id: str,
    work_order: str,
    expected_criteria: int = 3,
    resume: SubAgentResume | None = None,
) -> FrameResult | SubAgentApprovalWait:
    """Run FRAME and apply its result, on a fresh dispatch or a resumed one."""
    agent_deps = agent_deps_for(deps)
    if not agent_deps.agent_state.operational_spec_draft.goal:
        agent_deps.agent_state.operational_spec_draft.goal = deps.state.user_prompt
    delta = await stream_sub_agent(
        run=PhaseRun("frame", work_order, expected_criteria),
        agent_deps=agent_deps,
        parent_tool_call_id=parent_tool_call_id,
        expected_output_type=FrameResult,
        deps=deps,
        resume=resume,
    )
    if isinstance(delta, SubAgentApprovalWait):
        return delta
    apply_agent_state(deps, agent_deps)
    if delta is None:
        return frame_result_from_draft(deps.state.domain.operational_spec)
    draft = agent_deps.agent_state.operational_spec_draft
    if delta.disposition == "spec_ready" and not any(c.bound for c in draft.criteria):
        if deps.empty_frame_reported:
            return frame_bound_nothing_result()
        deps.empty_frame_reported = True
        refuse_and_restore(deps, frame_claimed_more_than_it_bound(delta.summary))
    before = deps.state.domain.spec_before_turn
    if before is not None and before.criteria:
        problem = undeclared_spec_changes(
            diff_specs(before, draft), delta.changes, before
        )
        if problem:
            refuse_and_restore(deps, problem)
    return delta


async def frame_problem(
    ctx: RunContext[LeadDeps], reason: str, expected_criteria: int = 3
) -> FrameResult:
    """Run the FRAME sub-agent: operationalize the goal into a realizable
    OperationalSpec - criteria bound to real WDK searches with auto-resolved
    params + a combine structure. Call this FIRST, then ``build_strategy``.
    Returns a ``FrameResult`` (disposition ``needs_user`` when criteria have
    open param slots the user must fill).

    ``expected_criteria`` is how many distinct filters the goal states - count
    the "and"s in the request. It sizes FRAME's tool budget, so undercounting a
    large request makes it run out before it binds them all.

    Available once per turn, while the thread has no strategy to change with
    ``edit_strategy`` and no empty build waiting on the user."""
    tool_call_id = dispatch_call_id(ctx)
    result = await run_frame(
        deps=ctx.deps,
        parent_tool_call_id=tool_call_id,
        work_order=frame_work_order(reason, ctx.deps.state.user_prompt),
        expected_criteria=expected_criteria,
    )
    if isinstance(result, SubAgentApprovalWait):
        defer_dispatch(ctx.deps, tool_call_id, result)
        return result
    ctx.deps.state.turn_markers.framed = True
    return result


async def build_strategy(ctx: RunContext[LeadDeps]) -> ExecuteDelta:
    """Materialize the OperationalSpec into a real WDK strategy declaratively
    (no LLM). Requires ``frame_problem`` first. Inspect ``ledger.build`` after
    to decide ``recover_failed_steps`` or ``verify_strategy``.

    Available while the thread holds no strategy: it would replace one that
    exists. Call ``edit_strategy`` to change a strategy, or ask the user how
    to start over."""
    deps = ctx.deps
    graph = deps.runtime.strategy_session.get_graph(None)
    if graph is not None and graph.steps:
        raise ModelRetry(build_would_replace_the_strategy(len(graph.steps)))
    spec = deps.state.domain.operational_spec
    if spec is None or not spec.ready_to_build:
        raise ModelRetry(build_not_ready_message(spec))
    # Readiness says every criterion is bound and a structure exists. Only the
    # conversion knows whether that structure is a tree WDK can hold.
    try:
        built = build_step_tree(spec)
    except ValueError as exc:
        msg = (
            f"The spec is bound but its structure does not convert: {exc}. "
            "Call set_structure with a tree whose every combine names an "
            "operator and joins two inputs."
        )
        raise ModelRetry(msg) from exc
    agent_deps = agent_deps_for(deps)
    outcome: BuildOutcome = await build_strategy_from_spec(
        deps=agent_deps.to_strategy_context(),
        root=built.root,
        name=spec.title or None,
    )
    # A criterion and the step it built become one address, so the next turn's
    # edit changes that step instead of rebuilding the strategy around it.
    deps.state.domain.operational_spec = renumber_criteria(
        spec, built.step_id_by_criterion
    )
    deps.state.record_build(outcome)
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


async def run_recovery(
    *,
    deps: LeadDeps,
    parent_tool_call_id: str,
    reason: str,
    resume: SubAgentResume | None = None,
) -> RecoveryDelta | SubAgentApprovalWait:
    """Run recovery and re-sync the build, on a fresh dispatch or a resumed one."""
    outcome = deps.state.domain.last_build_outcome
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
    agent_deps = agent_deps_for(deps)
    streamed = await stream_sub_agent(
        run=PhaseRun("execution", work_order),
        agent_deps=agent_deps,
        parent_tool_call_id=parent_tool_call_id,
        expected_output_type=RecoveryDelta,
        deps=deps,
        resume=resume,
    )
    if isinstance(streamed, SubAgentApprovalWait):
        return streamed
    apply_agent_state(deps, agent_deps)
    delta = streamed if streamed is not None else RecoveryDelta()
    deps.state.record_build(await _resync_outcome(agent_deps, outcome))
    return delta


async def recover_failed_steps(
    ctx: RunContext[LeadDeps],
    reason: str,
) -> RecoveryDelta:
    """Run the LLM execution-recovery sub-agent on a failed build.

    Only valid when ``ledger.build.needs_recovery`` is True and the
    failure shape is amenable to targeted edits (param replan, partial
    build). When a criterion needs a different search entirely, re-bind it
    with ``edit_strategy``, or tell the researcher which criterion needs a
    different search and end the turn.
    """
    tool_call_id = dispatch_call_id(ctx)
    result = await run_recovery(
        deps=ctx.deps,
        parent_tool_call_id=tool_call_id,
        reason=reason,
    )
    if isinstance(result, SubAgentApprovalWait):
        defer_dispatch(ctx.deps, tool_call_id, result)
    return result


async def _resync_outcome(agent_deps: AgentDeps, prior: BuildOutcome) -> BuildOutcome:
    """Re-derive the BuildOutcome after recovery edits by re-syncing the
    strategy. The recovery agent no longer emits the outcome itself."""
    graph = agent_deps.strategy_session.get_graph(None)
    if graph is None:
        return prior
    sync_state = ensure_sync_state(agent_deps.strategy_session)
    try:
        sync_result = await sync_strategy_for_site(
            graph=graph,
            sync_state=sync_state,
            site_id=agent_deps.site_id,
            strategy_name=graph.name,
        )
    except AppError:
        return prior
    fresh = BuildOutcome(
        pushed_step_ids=list(prior.pushed_step_ids),
        wdk_strategy_id=sync_result.wdk_strategy_id,
        wdk_url=sync_result.wdk_url,
        counts={str(k): v for k, v in sync_result.counts.items()},
        root_count=sync_result.root_count,
        zero_step_ids=list(sync_result.zero_step_ids),
    )
    fresh.node_results = node_results(list(graph.steps.values()), sync_state, fresh)
    return fresh


def verification_scope(
    deps: LeadDeps, *, enrichment_requested: bool
) -> VerificationScope:
    """What this turn changed, as the verification playbook reads it."""
    diff = derive_ledger(deps.state, deps.intent).frame.spec_diff()
    if diff is None:
        return VerificationScope(enrichment_requested=enrichment_requested)
    return VerificationScope(
        criteria_touched=diff.touched_count(),
        is_edit=True,
        enrichment_requested=enrichment_requested,
    )


async def run_verification(
    *,
    deps: LeadDeps,
    parent_tool_call_id: str,
    reason: str,
    enrichment_requested: bool = False,
    resume: SubAgentResume | None = None,
) -> VerificationDelta | SubAgentApprovalWait:
    """Run verification and record its digest, on a fresh or a resumed dispatch."""
    deps.state.turn_markers.verification_dispatched = True
    work_order = (
        f"Verification work order: {reason}\n"
        "Inspect the built strategy. Return a VerificationDelta."
    )
    agent_deps = agent_deps_for(deps)
    agent_deps.verification_scope = verification_scope(
        deps, enrichment_requested=enrichment_requested
    )
    delta = await stream_sub_agent(
        run=PhaseRun("verification", work_order),
        agent_deps=agent_deps,
        parent_tool_call_id=parent_tool_call_id,
        expected_output_type=VerificationDelta,
        deps=deps,
        resume=resume,
    )
    if isinstance(delta, SubAgentApprovalWait):
        return delta
    apply_agent_state(deps, agent_deps)
    if delta is None:
        msg = "Verification sub-agent did not return a VerificationDelta."
        raise TypeError(msg)
    digest = _digest_the_build_supports(deps, delta.digest)
    deps.state.domain.verification_digest = digest
    deps.state.turn_markers.verified = digest.success
    return VerificationDelta(digest=digest)


def _digest_the_build_supports(
    deps: LeadDeps, digest: VerificationDigest
) -> VerificationDigest:
    """Hold the verdict to what the ledger recorded.

    The digest decides the reply, the memory auto-write and the eval verdict,
    so a success it cannot support is corrected here rather than at each
    reader.
    """
    if not digest.success:
        return digest
    ledger = derive_ledger(deps.state, deps.intent)
    contradiction = build_contradiction(
        ledger.build,
        built_step_count=len(live_wdk_step_ids(deps.runtime.strategy_session)),
    )
    if contradiction is None:
        return digest
    return digest_held_to_the_build(digest, contradiction)


async def verify_strategy(
    ctx: RunContext[LeadDeps],
    reason: str,
    *,
    enrichment_requested: bool = False,
) -> VerificationDelta:
    """Run the verification sub-agent on the built strategy.

    This sub-agent owns every post-build check, so route a user's request for
    one here through ``reason``: GO, pathway and word enrichment on a gene
    set; control tests on a step or a search; parameter optimization; sample
    records from a result; result export. None of these are Lead tools.

    Set ``enrichment_requested`` only when the user asked for GO, pathway or
    word enrichment in this message. It runs for minutes on a worker, so an
    edit turn that did not ask for it is verified by its counts instead.

    Available once the strategy holds a step, and until a verification of this
    turn reports success.
    """
    tool_call_id = dispatch_call_id(ctx)
    result = await run_verification(
        deps=ctx.deps,
        parent_tool_call_id=tool_call_id,
        reason=reason,
        enrichment_requested=enrichment_requested,
    )
    if isinstance(result, SubAgentApprovalWait):
        defer_dispatch(ctx.deps, tool_call_id, result)
    return result
