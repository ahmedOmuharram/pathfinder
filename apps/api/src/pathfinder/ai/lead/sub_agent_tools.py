"""Sub-agent tool wrappers — invoked by the Lead Agent.

Each wrapper:
  1. Builds a focused work-order prompt from the Lead's input args.
  2. Constructs ``AgentDeps`` for the phase agent from ``LeadDeps.state``.
  3. Runs the phase agent (or runs declarative execution).
  4. Applies the typed delta back into ``LeadDeps.state`` (mutates the
     working PipelineState copy that the Lead's node will return to
     LangGraph at turn end).
  5. Returns the delta to the Lead.

The phase agents and their prompts/toolsets are unchanged from Stage 3 —
they just emit typed deltas instead of PhaseOutcome.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from langgraph.config import get_stream_writer
from pydantic import BaseModel
from pydantic_ai import AgentRunResultEvent, RunContext
from pydantic_ai.messages import (
    AgentStreamEvent,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    PartEndEvent,
    RetryPromptPart,
    TextPart,
    ThinkingPart,
)
from pydantic_ai.usage import RunUsage, UsageLimits

from pathfinder.ai.agents.discovery import discovery_agent
from pathfinder.ai.agents.execution import execution_agent
from pathfinder.ai.agents.planning import planning_agent
from pathfinder.ai.agents.roles import PhaseRole
from pathfinder.ai.agents.scoping import scoping_agent
from pathfinder.ai.agents.state import AgentToolState
from pathfinder.ai.agents.verification import verification_agent
from pathfinder.ai.graph.runtime import AgentDeps, Context
from pathfinder.ai.graph.state import PipelineState
from pathfinder.ai.graph.stream_events import (
    SubAgentStepPayload,
    ledger_update_event,
    sub_agent_step_event,
    turn_status_event,
)
from pathfinder.ai.lead.deltas import (
    DiscoveryDelta,
    ExecuteDelta,
    FrameDelta,
    PlanDelta,
    RecoveryDelta,
    VerificationDelta,
)
from pathfinder.ai.lead.derive import derive_ledger
from pathfinder.ai.lead.intent import UserIntent
from pathfinder.ai.memory.schemas import MemoryValue
from pathfinder.domain.strategy.build_outcome import BuildOutcome
from pathfinder.services.strategies.plan_to_spec import build_step_tree_from_plan
from pathfinder.services.strategies.spec_build import build_strategy_from_spec

PHASE_USAGE_LIMITS: UsageLimits = UsageLimits(
    request_limit=60,
    tool_calls_limit=60,
    total_tokens_limit=2_000_000,
)

_SUB_AGENT_BY_ROLE: dict[PhaseRole, Any] = {
    "scoping": scoping_agent,
    "discovery": discovery_agent,
    "planning": planning_agent,
    "execution": execution_agent,
    "verification": verification_agent,
}

TOOL_TO_PHASE_ROLE: dict[str, PhaseRole] = {
    "scope_problem": "scoping",
    "discover_searches": "discovery",
    "build_plan": "planning",
    "recover_failed_steps": "execution",
    "verify_strategy": "verification",
}


def sub_agent_model_id(tool_name: str) -> str:
    """Model id for a sub-agent tool name. ``execute_plan`` is declarative
    (no LLM); everything else maps to the underlying phase agent's model.
    """
    if tool_name == "execute_plan":
        return "declarative:no-llm"
    role = TOOL_TO_PHASE_ROLE.get(tool_name)
    if role is None:
        return ""
    model = _SUB_AGENT_BY_ROLE[role].model
    if model is None:
        return ""
    if isinstance(model, str):
        return model
    return str(model.model_id)


@dataclass
class SubAgentRunUsage:
    """Per-run usage from one sub-agent dispatch — fed back to lead_node so
    sub-agent tokens roll into the cumulative turn cost using the
    sub-agent's own model pricing (the Lead's pricing would be wrong;
    Lead is gpt-4.1, sub-agents are gpt-4.1-mini)."""

    usage: RunUsage
    model_name: str | None
    provider_name: str | None
    provider_url: str | None


@dataclass
class LeadDeps:
    """The Lead Agent's runtime context.

    Mutates ``state`` in place as sub-agent tools run; the Lead's node
    turns the final ``state`` into a langgraph state delta at turn end.
    """

    state: PipelineState
    intent: UserIntent | None
    runtime: Context
    retrieved_memories: list[MemoryValue]
    record_sub_agent_usage: Callable[[SubAgentRunUsage], None] = field(
        default=lambda _u: None,
    )


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
        experiment_id=runtime.experiment_id,
        cancel_event=runtime.cancel_event,
        memory_store=runtime.memory_store,
        retrieved_memories=deps.retrieved_memories,
        conversation_id=state.conversation_id,
        db_session_factory=runtime.db_session_factory,
        plan_slot_answers=_slot_answers(state),
    )


def _slot_answers(state: PipelineState) -> list:  # type: ignore[type-arg]
    pending = state.pending_approval
    if pending is None:
        return []
    return list(state.plan_slot_answers.get(pending.tool_call_id, []))


def _apply_agent_state(deps: LeadDeps, agent_deps: AgentDeps) -> None:
    deps.state.discovered_searches = dict(
        agent_deps.agent_state.discovered_searches,
    )
    deps.state.active_plan = agent_deps.agent_state.active_plan
    if agent_deps.problem_frame is not None:
        deps.state.problem_frame = agent_deps.problem_frame




def _emit_step(writer: Any, payload: SubAgentStepPayload) -> None:
    writer(
        {
            "chunk": sub_agent_step_event(payload).model_dump(
                by_alias=True, mode="json", exclude_none=True,
            ),
        },
    )


def _short(s: str, *, limit: int = 280) -> str:
    return s if len(s) <= limit else s[:limit] + "…"


def _summarize_tool_result(content: object) -> str:
    if isinstance(content, BaseModel):
        return _short(repr(content.model_dump(mode="json")))
    if isinstance(content, str):
        return _short(content)
    return _short(repr(content))


def _forward_inner_event(
    *,
    parent_tool_call_id: str,
    writer: Any,
    inner_calls: dict[str, str],
    event: AgentStreamEvent,
) -> None:
    """Translate one inner-agent stream event into a
    ``data-sub-agent-step`` chunk for the frontend."""
    if isinstance(event, FunctionToolCallEvent):
        inner_calls[event.tool_call_id] = event.part.tool_name
        _emit_step(
            writer,
            SubAgentStepPayload(
                parent_tool_call_id=parent_tool_call_id,
                kind="tool",
                state="started",
                tool_call_id=event.tool_call_id,
                tool_name=event.part.tool_name,
                args=event.part.args_as_dict(),
            ),
        )
        return
    if isinstance(event, FunctionToolResultEvent):
        tool_name = inner_calls.get(event.tool_call_id)
        if tool_name is None:
            return
        result = event.result
        is_retry = isinstance(result, RetryPromptPart)
        if is_retry:
            content = result.content
            summary = (
                _short(content)
                if isinstance(content, str)
                else "retry requested"
            )
        else:
            summary = _summarize_tool_result(result.content)
        _emit_step(
            writer,
            SubAgentStepPayload(
                parent_tool_call_id=parent_tool_call_id,
                kind="tool",
                state="failed" if is_retry else "completed",
                tool_call_id=event.tool_call_id,
                tool_name=tool_name,
                result_summary=summary,
            ),
        )
        return
    if isinstance(event, PartEndEvent):
        part = event.part
        if isinstance(part, TextPart) and part.content.strip():
            _emit_step(
                writer,
                SubAgentStepPayload(
                    parent_tool_call_id=parent_tool_call_id,
                    kind="text",
                    state="completed",
                    text=_short(part.content, limit=2000),
                ),
            )
        elif isinstance(part, ThinkingPart) and part.content.strip():
            _emit_step(
                writer,
                SubAgentStepPayload(
                    parent_tool_call_id=parent_tool_call_id,
                    kind="reasoning",
                    state="completed",
                    text=_short(part.content, limit=2000),
                ),
            )


def _phase_override_kwargs(
    runtime: Context, role: PhaseRole,
) -> dict[str, Any]:
    """Build kwargs for ``agent.override`` from the per-phase Context maps."""
    kwargs: dict[str, Any] = {}
    model_override = runtime.phase_models.get(role)
    if model_override:
        kwargs["model"] = model_override
    effort = runtime.phase_reasoning.get(role)
    if effort in ("low", "medium", "high"):
        kwargs["model_settings"] = {"thinking": effort}
    return kwargs


_PHASE_STATUS_LABELS: dict[PhaseRole, str] = {
    "lead": "Thinking...",
    "scoping": "Scoping the problem...",
    "discovery": "Finding searches...",
    "planning": "Building a plan...",
    "execution": "Recovering failed steps...",
    "verification": "Verifying the strategy...",
}


async def _stream_sub_agent[OutputT: BaseModel](
    *,
    role: PhaseRole,
    work_order: str,
    agent_deps: AgentDeps,
    parent_tool_call_id: str,
    expected_output_type: type[OutputT],
    deps: LeadDeps,
) -> OutputT | None:
    agent = _SUB_AGENT_BY_ROLE[role]
    """Run a sub-agent, forward its inner events as
    ``data-sub-agent-step`` chunks, push its usage into the Lead's
    accumulator (using the sub-agent's own model for cost attribution),
    and return the typed delta."""
    writer = get_stream_writer()
    inner_calls: dict[str, str] = {}
    output: OutputT | None = None
    usage = RunUsage()
    override_kwargs = _phase_override_kwargs(deps.runtime, role)
    override_ctx = (
        agent.override(**override_kwargs)
        if override_kwargs
        else contextlib.nullcontext()
    )
    writer(
        {
            "chunk": turn_status_event(
                label=_PHASE_STATUS_LABELS.get(role, "Working..."),
                waiting_on_llm=True,
            ).model_dump(by_alias=True, mode="json", exclude_none=True),
        },
    )
    with override_ctx:
        async for event in agent.run_stream_events(
            work_order, deps=agent_deps,
            usage_limits=PHASE_USAGE_LIMITS, usage=usage,
        ):
            if isinstance(event, AgentRunResultEvent):
                agent_output = event.result.output
                if isinstance(agent_output, expected_output_type):
                    output = agent_output
                response = event.result.response
                deps.record_sub_agent_usage(
                    SubAgentRunUsage(
                        usage=event.result.usage(),
                        model_name=response.model_name,
                        provider_name=response.provider_name,
                        provider_url=response.provider_url,
                    ),
                )
                continue
            _forward_inner_event(
                parent_tool_call_id=parent_tool_call_id,
                writer=writer,
                inner_calls=inner_calls,
                event=event,
            )
            if isinstance(event, FunctionToolResultEvent):
                _emit_live_ledger(writer, deps, agent_deps)
    return output


def _emit_live_ledger(
    writer: Any, deps: LeadDeps, agent_deps: AgentDeps,
) -> None:
    """After every sub-agent tool call, sync state and broadcast a fresh
    ledger snapshot so the UI sees discovery decisions, plan edits, etc. as
    they happen instead of waiting for the sub-agent to return to the Lead.
    """
    _apply_agent_state(deps, agent_deps)
    ledger = derive_ledger(deps.state, deps.intent)
    writer(
        {
            "chunk": ledger_update_event(ledger=ledger).model_dump(
                by_alias=True, mode="json", exclude_none=True,
            ),
        },
    )


def _parent_tool_call_id(ctx: RunContext[LeadDeps]) -> str:
    """The Lead's tool_call_id for the active sub-agent dispatch.
    Always present when invoked through the Lead's toolset; defensively
    returns an empty string if missing so we never crash on telemetry."""
    return ctx.tool_call_id or ""


async def scope_problem(
    ctx: RunContext[LeadDeps], reason: str,
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
    return delta


async def discover_searches(
    ctx: RunContext[LeadDeps],
    reason: str,
    intent_summary: str,
    hints: str = "",
) -> DiscoveryDelta:
    """Run the discovery sub-agent to find WDK searches.

    ``hints`` carries Lead-derived guidance (e.g. "vocab gap: prior
    selection covers gametocyte but not asexual blood stages — find a
    search whose vocab spans both"). The sub-agent commits selections
    via ``update_search_decision``; we mirror those onto LeadDeps.state.
    """
    deps = ctx.deps
    work_order_parts = [
        f"Discovery work order: {reason}",
        f"Intent: {intent_summary}",
    ]
    if hints:
        work_order_parts.append(f"Hints: {hints}")
    work_order_parts.append("Return a DiscoveryDelta.")
    work_order = "\n".join(work_order_parts)
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
    return delta


async def build_plan(
    ctx: RunContext[LeadDeps], reason: str,
) -> PlanDelta:
    """Run the planning sub-agent to construct a strategy plan.

    The sub-agent does NOT submit the plan — it only authors it. The
    Lead is responsible for surfacing the plan to the user via its own
    ``submit_plan_for_approval`` deferred-tool.
    """
    deps = ctx.deps
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
    if delta is not None:
        return delta
    plan = agent_deps.agent_state.active_plan
    if plan is None:
        msg = "Planning sub-agent returned no plan."
        raise RuntimeError(msg)
    return PlanDelta(plan=plan)


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
        deps=agent_deps, root=root, name=plan.title or None,
    )
    deps.state.last_build_outcome = outcome
    return ExecuteDelta(outcome=outcome)


async def recover_failed_steps(
    ctx: RunContext[LeadDeps], reason: str,
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
    delta = streamed if streamed is not None else RecoveryDelta(
        final_outcome=outcome,
    )
    deps.state.last_build_outcome = delta.final_outcome
    return delta


async def verify_strategy(
    ctx: RunContext[LeadDeps], reason: str,
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
