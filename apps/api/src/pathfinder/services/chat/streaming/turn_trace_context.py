"""Trace context and span annotation helpers for streamed chat turns."""

from opentelemetry import trace

from pathfinder.ai.orchestration.classifier import Intent
from pathfinder.ai.orchestration.deps import AgentDeps
from pathfinder.ai.orchestration.observability import (
    annotate_span_with_observability_identity,
    get_observability_identity,
)
from pathfinder.ai.prompts.loader import PromptBundle
from pathfinder.platform.context import operation_id_ctx, stream_id_ctx
from pathfinder.platform.langfuse.otel import (
    LangfuseTraceAttributes,
    LangfuseTraceContext,
    propagate_langfuse_trace_context,
    set_langfuse_observation_attributes,
    set_langfuse_trace_attributes,
)
from pathfinder.platform.types import JSONObject
from pathfinder.services.chat.streaming.turn_telemetry import PhaseSpanContext
from pathfinder.services.chat.types import turn_metadata_trace_fields


def _turn_kind(deps: AgentDeps) -> str:
    """Return the user-facing kind of turn being processed."""
    return "plan_action" if deps.plan_action is not None else "chat"


def _turn_trace_tags(
    deps: AgentDeps,
    *,
    intent: Intent,
    run_kind: str,
) -> list[str]:
    """Return stable Langfuse tags shared across the turn and child spans."""
    return [deps.site_id, intent.value, run_kind, _turn_kind(deps)]


def _turn_trace_metadata(
    deps: AgentDeps,
    *,
    intent: Intent,
    run_kind: str,
    message_group_id: str | None,
) -> dict[str, object]:
    """Return stable turn lineage metadata for Langfuse filtering."""
    graph = deps.strategy_session.get_graph(None)
    active_plan = deps.agent_state.active_plan
    stream_id = stream_id_ctx.get()
    operation_id = operation_id_ctx.get()
    return {
        "site_id": deps.site_id,
        "stream_id": stream_id,
        "operation_id": operation_id,
        "turn_id": operation_id,
        "turn_kind": _turn_kind(deps),
        "run_kind": run_kind,
        "intent": intent.value,
        "message_group_id": message_group_id,
        **turn_metadata_trace_fields(deps.turn_metadata),
        "graph_id": graph.id if graph is not None else None,
        "graph_name": graph.name if graph is not None else None,
        "record_type": graph.record_type if graph is not None else None,
        "plan_action": deps.plan_action.action if deps.plan_action is not None else None,
        "plan_action_source_trace_id": (
            deps.plan_action.source_trace_id if deps.plan_action is not None else None
        ),
        "plan_action_source_message_group_id": (
            deps.plan_action.source_message_group_id
            if deps.plan_action is not None
            else None
        ),
        "plan_action_source": (
            deps.plan_action.source if deps.plan_action is not None else None
        ),
        "plan_action_answer_count": (
            len(deps.plan_action.answered_question_ids)
            if deps.plan_action is not None
            else 0
        ),
        "plan_action_edit_count": (
            len(deps.plan_action.edited_params)
            if deps.plan_action is not None
            else 0
        ),
        "plan_action_presented_at": (
            deps.plan_action.presented_at.isoformat()
            if deps.plan_action is not None
            and deps.plan_action.presented_at is not None
            else None
        ),
        "plan_action_approved_at": (
            deps.plan_action.approved_at.isoformat()
            if deps.plan_action is not None and deps.plan_action.approved_at is not None
            else None
        ),
        "plan_action_approval_wait_ms": (
            deps.plan_action.approval_wait_ms if deps.plan_action is not None else None
        ),
        "plan_id": (
            deps.plan_action.plan_id
            if deps.plan_action is not None
            else active_plan.id if active_plan is not None else None
        ),
        "active_plan_id": active_plan.id if active_plan is not None else None,
        "active_plan_status": (
            active_plan.status.value if active_plan is not None else None
        ),
        "active_plan_step_count": len(active_plan.steps) if active_plan is not None else 0,
        "active_plan_question_count": (
            len(active_plan.questions) if active_plan is not None else 0
        ),
    }


def _turn_trace_context(
    deps: AgentDeps,
    *,
    intent: Intent,
    run_kind: str,
    message_group_id: str | None,
) -> LangfuseTraceContext:
    """Build stable Langfuse trace context for a turn and its child spans."""
    observability_identity = get_observability_identity()
    return LangfuseTraceContext(
        user_id=str(deps.user_id) if deps.user_id is not None else None,
        session_id=stream_id_ctx.get(),
        tags=tuple(_turn_trace_tags(deps, intent=intent, run_kind=run_kind)),
        metadata={
            **_turn_trace_metadata(
                deps,
                intent=intent,
                run_kind=run_kind,
                message_group_id=message_group_id,
            ),
            "service_name": observability_identity["service.name"],
            "service_version": observability_identity["service.version"],
            "deployment_environment": observability_identity[
                "deployment.environment.name"
            ],
        },
        release=observability_identity["service.version"],
        environment=observability_identity["deployment.environment.name"],
    )


def _annotate_current_turn_span(
    deps: AgentDeps,
    *,
    intent: Intent,
    run_kind: str,
    message_group_id: str | None,
    trace_name: str,
) -> None:
    """Update the current root span with stable Langfuse trace fields."""
    current_span = trace.get_current_span()
    if not current_span.is_recording():
        return
    current_span.update_name(trace_name)
    annotate_span_with_observability_identity(current_span)
    set_langfuse_trace_attributes(
        current_span,
        LangfuseTraceAttributes(name=trace_name),
        trace_ctx=_turn_trace_context(
            deps,
            intent=intent,
            run_kind=run_kind,
            message_group_id=message_group_id,
        ),
    )


def _set_phase_span_attributes(
    span: trace.Span,
    deps: AgentDeps,
    *,
    span_ctx: PhaseSpanContext,
    phase_input: JSONObject,
    prompt_bundle: PromptBundle,
) -> None:
    """Set app + GenAI semantic convention attributes on a phase span."""
    phase = span_ctx.phase
    intent = span_ctx.event.intent
    model_id = span_ctx.event.model_id
    run_kind = span_ctx.event.run_kind
    trace_context = _turn_trace_context(
        deps,
        intent=intent,
        run_kind=run_kind,
        message_group_id=span_ctx.message_group_id,
    )
    trace_metadata = dict(trace_context.metadata or {})
    graph = deps.strategy_session.get_graph(None)

    annotate_span_with_observability_identity(span)
    span.set_attribute("app.phase", phase)
    span.set_attribute("app.intent", intent.value)
    span.set_attribute("app.run_kind", run_kind)
    span.set_attribute("app.turn_kind", _turn_kind(deps))
    if trace_metadata["stream_id"] is not None:
        span.set_attribute("app.stream_id", str(trace_metadata["stream_id"]))
    if trace_metadata["operation_id"] is not None:
        span.set_attribute("app.operation_id", str(trace_metadata["operation_id"]))
    if span_ctx.message_group_id is not None:
        span.set_attribute("app.message_group_id", span_ctx.message_group_id)
    if trace_metadata["plan_id"] is not None:
        span.set_attribute("app.plan_id", str(trace_metadata["plan_id"]))
    span.set_attribute("gen_ai.agent.name", phase)
    span.set_attribute("gen_ai.operation.name", "invoke_agent")
    span.set_attribute("gen_ai.request.model", model_id)
    if graph is not None:
        span.set_attribute("gen_ai.conversation.id", graph.id)
    propagate_langfuse_trace_context(span, trace_context)
    set_langfuse_observation_attributes(
        span,
        observation_type="agent",
        input_value=phase_input,
        metadata={
            "phase": phase,
            "intent": intent.value,
            "run_kind": run_kind,
            "message_group_id": span_ctx.message_group_id,
            "configured_model": model_id,
            "has_turn_metadata": bool(deps.turn_metadata),
            "turn_metadata_keys": sorted(deps.turn_metadata),
            "has_context_summary": deps.context_summary is not None,
            "has_problem_frame": deps.problem_frame is not None,
            "has_approved_plan": deps.approved_plan is not None,
            "active_plan_id": trace_metadata["active_plan_id"],
            **prompt_bundle.langfuse_metadata(),
        },
    )
