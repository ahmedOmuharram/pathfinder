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
from pathfinder.ai.lead.deltas import (
    ExecuteDelta,
    FrameResult,
    RecoveryDelta,
    VerificationDelta,
)
from pathfinder.ai.lead.derive import derive_ledger
from pathfinder.ai.lead.sub_agent_tools import (
    LeadDeps,
    _apply_agent_state,
    _stream_sub_agent,
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
            discovered_searches=dict(state.discovered_searches),
            operational_spec_draft=state.operational_spec
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


async def frame_problem(ctx: RunContext[LeadDeps], reason: str) -> FrameResult:
    """Run the FRAME sub-agent: operationalize the goal into a realizable
    OperationalSpec — criteria bound to real WDK searches with auto-resolved
    params + a combine structure. Call this FIRST, then ``build_strategy``.
    Returns a ``FrameResult`` (disposition ``needs_user`` when criteria have
    open param slots the user must fill)."""
    deps = ctx.deps
    work_order = (
        f"FRAME work order: {reason}\n"
        f"User's goal: {deps.state.user_prompt}\n"
        "Operationalize into criteria, bind each to a real WDK search, resolve "
        "params, set the structure. Return a FrameResult."
    )
    agent_deps = _agent_deps(deps)
    if not agent_deps.agent_state.operational_spec_draft.goal:
        agent_deps.agent_state.operational_spec_draft.goal = deps.state.user_prompt
    delta = await _stream_sub_agent(
        role="frame",
        work_order=work_order,
        agent_deps=agent_deps,
        parent_tool_call_id=_parent_tool_call_id(ctx),
        expected_output_type=FrameResult,
        deps=deps,
    )
    _apply_agent_state(deps, agent_deps)
    if delta is None:
        return FrameResult(
            disposition="needs_user", summary="FRAME returned no result."
        )
    return delta


async def build_strategy(ctx: RunContext[LeadDeps]) -> ExecuteDelta:
    """Materialize the OperationalSpec into a real WDK strategy declaratively
    (no LLM). Requires ``frame_problem`` first. Inspect ``ledger.build`` after
    to decide ``recover_failed_steps`` or ``verify_strategy``."""
    deps = ctx.deps
    spec = deps.state.operational_spec
    if spec is None or not spec.ready_to_build:
        msg = (
            "OperationalSpec is not ready to build (no criteria/structure, or "
            "open param slots need user input). Call frame_problem first."
        )
        raise ModelRetry(msg)
    root = operational_spec_to_step_tree(spec)
    agent_deps = _agent_deps(deps)
    outcome: BuildOutcome = await build_strategy_from_spec(
        deps=agent_deps.to_strategy_context(),
        root=root,
        name=spec.title or None,
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
    build). When a criterion needs a different search entirely, the Lead
    should call ``frame_problem`` again to re-bind the spec instead.
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
    delta = streamed if streamed is not None else RecoveryDelta()
    deps.state.last_build_outcome = await _resync_outcome(agent_deps, outcome)
    return delta


async def _resync_outcome(agent_deps: AgentDeps, prior: BuildOutcome) -> BuildOutcome:
    """Re-derive the BuildOutcome after recovery edits by re-syncing the
    strategy — the recovery agent no longer emits the outcome itself."""
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
