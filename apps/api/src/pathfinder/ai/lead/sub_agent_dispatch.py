"""The Lead Agent's sub-agent dispatch tools.

The tool wrappers the Lead invokes to run a phase sub-agent, the
``AgentDeps`` construction they share, and the re-entry that finishes one
after the user answers an approval.
"""

from __future__ import annotations

from typing import NoReturn

from assistant_core.graph.turn_state import PendingApproval
from langgraph.config import get_stream_writer
from pydantic import BaseModel, ConfigDict
from pydantic_ai import RunContext
from pydantic_ai.exceptions import CallDeferred, ModelRetry

from pathfinder.ai.agents.state import AgentToolState
from pathfinder.ai.graph.runtime import AgentDeps
from pathfinder.ai.lead.deltas import (
    ExecuteDelta,
    FrameResult,
    RecoveryDelta,
    VerificationDelta,
)
from pathfinder.ai.lead.derive import derive_ledger
from pathfinder.ai.lead.dispatch_messages import (
    build_not_ready_message,
    frame_result_from_draft,
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
from pathfinder.domain.strategy.build_outcome import BuildOutcome
from pathfinder.domain.strategy.operational_spec import (
    OperationalSpec,
    operational_spec_to_step_tree,
)
from pathfinder.platform.errors import AppError
from pathfinder.services.strategies.auto_import import (
    import_gene_set_for_conversation,
)
from pathfinder.services.strategies.spec_build import (
    _node_results,
    build_strategy_from_spec,
)
from pathfinder.services.strategies.sync import sync_strategy_for_site
from pathfinder.services.strategies.sync_state import ensure_sync_state


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
            discovered_searches=dict(state.domain.discovered_searches),
            operational_spec_draft=state.domain.operational_spec
            or OperationalSpec(goal=state.user_prompt),
        ),
        ledger_summary=derive_ledger(state, deps.intent).render_summary(),
        experiment_id=runtime.experiment_id,
        cancel_event=runtime.cancel_event,
        memory_store=runtime.memory_store,
        retrieved_memories=deps.retrieved_memories,
        conversation_id=state.conversation_id,
        db_session_factory=runtime.db_session_factory,
    )


def _parent_tool_call_id(ctx: RunContext[LeadDeps]) -> str:
    """The Lead's tool_call_id for the active sub-agent dispatch.
    Always present when invoked through the Lead's toolset; defensively
    returns an empty string if missing so we never crash on telemetry."""
    return ctx.tool_call_id or ""


def _defer_to_user(
    deps: LeadDeps,
    tool_call_id: str,
    wait: SubAgentApprovalWait,
) -> NoReturn:
    """End the Lead's run deferred so the user answers the sub-agent's tool."""
    deps.pending_sub_agent_approvals[tool_call_id] = wait.pending
    raise CallDeferred


async def run_frame(
    *,
    deps: LeadDeps,
    parent_tool_call_id: str,
    reason: str,
    expected_criteria: int = 3,
    resume: SubAgentResume | None = None,
) -> FrameResult | SubAgentApprovalWait:
    """Run FRAME and apply its result, on a fresh dispatch or a resumed one."""
    work_order = (
        f"FRAME work order: {reason}\n"
        f"User's goal: {deps.state.user_prompt}\n"
        "Operationalize into criteria, bind each to a real WDK search, resolve "
        "params, set the structure. Return a FrameResult."
    )
    agent_deps = _agent_deps(deps)
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
    return delta


async def frame_problem(
    ctx: RunContext[LeadDeps], reason: str, expected_criteria: int = 3
) -> FrameResult:
    """Run the FRAME sub-agent: operationalize the goal into a realizable
    OperationalSpec — criteria bound to real WDK searches with auto-resolved
    params + a combine structure. Call this FIRST, then ``build_strategy``.
    Returns a ``FrameResult`` (disposition ``needs_user`` when criteria have
    open param slots the user must fill).

    ``expected_criteria`` is how many distinct filters the goal states — count
    the "and"s in the request. It sizes FRAME's tool budget, so undercounting a
    large request makes it run out before it binds them all."""
    tool_call_id = _parent_tool_call_id(ctx)
    result = await run_frame(
        deps=ctx.deps,
        parent_tool_call_id=tool_call_id,
        reason=reason,
        expected_criteria=expected_criteria,
    )
    if isinstance(result, SubAgentApprovalWait):
        _defer_to_user(ctx.deps, tool_call_id, result)
    return result


async def build_strategy(ctx: RunContext[LeadDeps]) -> ExecuteDelta:
    """Materialize the OperationalSpec into a real WDK strategy declaratively
    (no LLM). Requires ``frame_problem`` first. Inspect ``ledger.build`` after
    to decide ``recover_failed_steps`` or ``verify_strategy``."""
    deps = ctx.deps
    spec = deps.state.domain.operational_spec
    if spec is None or not spec.ready_to_build:
        raise ModelRetry(build_not_ready_message(spec))
    # Readiness says every criterion is bound and a structure exists. Only the
    # conversion knows whether that structure is a tree WDK can hold.
    try:
        root = operational_spec_to_step_tree(spec)
    except ValueError as exc:
        msg = (
            f"The spec is bound but its structure does not convert: {exc}. "
            "Call set_structure with a tree whose every combine names an "
            "operator and joins two inputs."
        )
        raise ModelRetry(msg) from exc
    agent_deps = _agent_deps(deps)
    outcome: BuildOutcome = await build_strategy_from_spec(
        deps=agent_deps.to_strategy_context(),
        root=root,
        name=spec.title or None,
    )
    deps.state.domain.last_build_outcome = outcome
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
    agent_deps = _agent_deps(deps)
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
    deps.state.domain.last_build_outcome = await _resync_outcome(agent_deps, outcome)
    return delta


async def recover_failed_steps(
    ctx: RunContext[LeadDeps],
    reason: str,
) -> RecoveryDelta:
    """Run the LLM execution-recovery sub-agent on a failed build.

    Only valid when ``ledger.build.needs_recovery`` is True and the
    failure shape is amenable to targeted edits (param replan, partial
    build). When a criterion needs a different search entirely, the Lead
    should call ``frame_problem`` again to re-bind the spec instead.
    """
    tool_call_id = _parent_tool_call_id(ctx)
    result = await run_recovery(
        deps=ctx.deps,
        parent_tool_call_id=tool_call_id,
        reason=reason,
    )
    if isinstance(result, SubAgentApprovalWait):
        _defer_to_user(ctx.deps, tool_call_id, result)
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
    fresh.node_results = _node_results(list(graph.steps.values()), sync_state, fresh)
    return fresh


async def run_verification(
    *,
    deps: LeadDeps,
    parent_tool_call_id: str,
    reason: str,
    resume: SubAgentResume | None = None,
) -> VerificationDelta | SubAgentApprovalWait:
    """Run verification and record its digest, on a fresh or a resumed dispatch."""
    work_order = (
        f"Verification work order: {reason}\n"
        "Inspect the built strategy. Return a VerificationDelta."
    )
    agent_deps = _agent_deps(deps)
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
    deps.state.domain.verification_digest = delta.digest
    return delta


async def verify_strategy(
    ctx: RunContext[LeadDeps],
    reason: str,
) -> VerificationDelta:
    """Run the verification sub-agent on the built strategy.

    This sub-agent owns every post-build check, so route a user's request for
    one here through ``reason``: GO, pathway and word enrichment on a gene
    set; control tests on a step or a search; parameter optimization; sample
    records from a result; result export. None of these are Lead tools.
    """
    tool_call_id = _parent_tool_call_id(ctx)
    result = await run_verification(
        deps=ctx.deps,
        parent_tool_call_id=tool_call_id,
        reason=reason,
    )
    if isinstance(result, SubAgentApprovalWait):
        _defer_to_user(ctx.deps, tool_call_id, result)
    return result


class _ReasonArgs(BaseModel):
    """The ``reason`` every dispatch wrapper takes."""

    model_config = ConfigDict(extra="ignore")

    reason: str = ""


class _FrameArgs(_ReasonArgs):
    expected_criteria: int = 3


async def resume_sub_agent(
    *,
    deps: LeadDeps,
    approval: PendingApproval,
    resume: SubAgentResume,
) -> FrameResult | RecoveryDelta | VerificationDelta | SubAgentApprovalWait:
    """Finish the dispatch the user answered, from its own arguments."""
    call_id = approval.tool_call_id
    args = dict(approval.tool_args)
    match approval.tool_name:
        case "verify_strategy":
            return await run_verification(
                deps=deps,
                parent_tool_call_id=call_id,
                reason=_ReasonArgs.model_validate(args).reason,
                resume=resume,
            )
        case "recover_failed_steps":
            return await run_recovery(
                deps=deps,
                parent_tool_call_id=call_id,
                reason=_ReasonArgs.model_validate(args).reason,
                resume=resume,
            )
        case "frame_problem":
            frame_args = _FrameArgs.model_validate(args)
            return await run_frame(
                deps=deps,
                parent_tool_call_id=call_id,
                reason=frame_args.reason,
                expected_criteria=frame_args.expected_criteria,
                resume=resume,
            )
        case _:
            msg = f"No sub-agent dispatch named {approval.tool_name!r} to resume."
            raise RuntimeError(msg)
