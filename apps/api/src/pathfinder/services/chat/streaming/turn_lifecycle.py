"""Lifecycle, metrics, and error helpers for streamed chat turns."""

import asyncio
import time
from datetime import UTC, datetime

from opentelemetry import trace
from opentelemetry.metrics import Histogram
from pydantic_ai.exceptions import UsageLimitExceeded

from pathfinder.ai.models.pricing import estimate_cost
from pathfinder.platform.errors import sanitize_error_for_client
from pathfinder.platform.event_schemas import ErrorEventData, MessageEndEventData
from pathfinder.platform.event_schemas_pipeline import PhaseChangeEventData
from pathfinder.platform.langfuse.otel import (
    LangfuseTraceAttributes,
    LangfuseTraceContext,
    set_langfuse_trace_attributes,
)
from pathfinder.platform.logging import get_logger
from pathfinder.platform.metrics import (
    phase_duration_s,
    pipeline_approval_wait_s,
    pipeline_errors,
    pipeline_execution_duration_s,
    pipeline_phase_events,
    pipeline_recoveries,
    pipeline_resume_after_approval_s,
    pipeline_runs,
    pipeline_time_to_first_assistant_delta_s,
    pipeline_time_to_first_assistant_message_s,
    pipeline_time_to_first_tool_call_s,
    pipeline_turn_duration_s,
    token_usage,
)
from pathfinder.platform.types import JSONObject
from pathfinder.services.chat.streaming.events import emit_phase_event
from pathfinder.services.chat.streaming.node_streaming import TurnCounters
from pathfinder.services.chat.streaming.turn_payloads import build_turn_output_payload
from pathfinder.services.chat.streaming.turn_telemetry import (
    PhaseEventContext,
    PhaseTimingSnapshot,
    TurnFailureContext,
    TurnLatencySummary,
    TurnTelemetryContext,
)

logger = get_logger(__name__)


def _surface_for_run_kind(run_kind: str) -> str:
    if run_kind == "plan_approval":
        return "plan_action"
    if run_kind == "chat":
        return "chat"
    return run_kind


def _phase_metric_attrs(
    *,
    phase: str,
    status: str,
    phase_ctx: PhaseEventContext,
) -> dict[str, str]:
    return {
        "phase": phase,
        "status": status,
        "intent": phase_ctx.intent.value,
        "model": phase_ctx.model_id,
        "run_kind": phase_ctx.run_kind,
        "surface": _surface_for_run_kind(phase_ctx.run_kind),
    }


def _record_phase_metrics(
    *,
    snapshot: PhaseTimingSnapshot,
    phase_ctx: PhaseEventContext,
) -> None:
    attrs = _phase_metric_attrs(
        phase=snapshot.phase,
        status=snapshot.status,
        phase_ctx=phase_ctx,
    )
    pipeline_phase_events.add(1, attrs)
    if snapshot.status != "started" and snapshot.duration_ms is not None:
        phase_duration_s.record(snapshot.duration_ms / 1000, attrs)


def _log_phase_status(
    *,
    snapshot: PhaseTimingSnapshot,
    phase_ctx: PhaseEventContext,
    message_id: str | None,
    message_group_id: str | None,
) -> None:
    log = logger.warning if snapshot.status == "failed" else logger.info
    log(
        "Pipeline phase update",
        phase=snapshot.phase,
        status=snapshot.status,
        attempt=snapshot.attempt,
        intent=phase_ctx.intent.value,
        model_id=phase_ctx.model_id,
        run_kind=phase_ctx.run_kind,
        message_id=message_id,
        message_group_id=message_group_id,
        emitted_at=snapshot.emitted_at,
        phase_started_at=snapshot.phase_started_at,
        phase_completed_at=snapshot.phase_completed_at,
        duration_ms=snapshot.duration_ms,
    )


async def _emit_phase_status(
    queue: asyncio.Queue[JSONObject],
    *,
    phase_ctx: PhaseEventContext,
    snapshot: PhaseTimingSnapshot,
    message_id: str | None = None,
    message_group_id: str | None = None,
) -> None:
    """Emit a phase status event and record the associated observability data."""
    await emit_phase_event(
        queue,
        PhaseChangeEventData.model_validate({
            "phase": snapshot.phase,
            "status": snapshot.status,
            "message_id": message_id,
            "message_group_id": message_group_id,
            "emitted_at": snapshot.emitted_at,
            "phase_started_at": snapshot.phase_started_at,
            "phase_completed_at": snapshot.phase_completed_at,
            "duration_ms": snapshot.duration_ms,
        }),
    )
    _record_phase_metrics(snapshot=snapshot, phase_ctx=phase_ctx)
    _log_phase_status(
        snapshot=snapshot,
        phase_ctx=phase_ctx,
        message_id=message_id,
        message_group_id=message_group_id,
    )


def _record_turn_metrics(
    outcome: str,
    turn_ctx: TurnTelemetryContext,
    counters: TurnCounters,
    *,
    total_duration_ms: int,
    latency_summary: TurnLatencySummary,
) -> None:
    """Record pipeline-level OTEL metrics for a completed turn."""
    attrs = {
        "intent": turn_ctx.intent.value,
        "outcome": outcome,
        "model": turn_ctx.model_id,
        "run_kind": turn_ctx.run_kind,
        "surface": _surface_for_run_kind(turn_ctx.run_kind),
    }
    pipeline_runs.add(1, attrs)
    pipeline_turn_duration_s.record(total_duration_ms / 1000, attrs)
    token_usage.add(
        counters.input_tokens,
        {
            "model": turn_ctx.model_id,
            "type": "input",
            "intent": turn_ctx.intent.value,
            "run_kind": turn_ctx.run_kind,
            "surface": attrs["surface"],
        },
    )
    token_usage.add(
        counters.output_tokens,
        {
            "model": turn_ctx.model_id,
            "type": "output",
            "intent": turn_ctx.intent.value,
            "run_kind": turn_ctx.run_kind,
            "surface": attrs["surface"],
        },
    )
    token_usage.add(
        counters.cache_read_tokens,
        {
            "model": turn_ctx.model_id,
            "type": "cached",
            "intent": turn_ctx.intent.value,
            "run_kind": turn_ctx.run_kind,
            "surface": attrs["surface"],
        },
    )
    _record_optional_turn_latency(
        pipeline_time_to_first_assistant_delta_s,
        latency_summary.time_to_first_assistant_delta_ms,
        attrs,
    )
    _record_optional_turn_latency(
        pipeline_time_to_first_assistant_message_s,
        latency_summary.time_to_first_assistant_message_ms,
        attrs,
    )
    _record_optional_turn_latency(
        pipeline_time_to_first_tool_call_s,
        latency_summary.time_to_first_tool_call_ms,
        attrs,
    )
    _record_optional_turn_latency(
        pipeline_approval_wait_s,
        latency_summary.approval_wait_ms,
        attrs,
    )
    _record_optional_turn_latency(
        pipeline_resume_after_approval_s,
        latency_summary.resume_after_approval_ms,
        attrs,
    )
    _record_optional_turn_latency(
        pipeline_execution_duration_s,
        latency_summary.execution_duration_ms,
        attrs,
    )
    for recovery in turn_ctx.runtime.recoveries:
        pipeline_recoveries.add(
            1,
            {
                **attrs,
                "phase": recovery.phase,
                "kind": recovery.kind,
            },
        )


def _record_optional_turn_latency(
    metric: Histogram,
    value_ms: int | None,
    attrs: dict[str, str],
) -> None:
    if value_ms is not None:
        metric.record(value_ms / 1000, attrs)


def _set_turn_span_summary_attributes(
    *,
    total_duration_ms: int,
    latency_summary: TurnLatencySummary,
    counters: TurnCounters,
    outcome: str,
    failure_context: TurnFailureContext | None,
    recovery_count: int,
) -> None:
    current_span = trace.get_current_span()
    if not current_span.is_recording():
        return

    current_span.set_attribute("app.pipeline.outcome", outcome)
    current_span.set_attribute("app.pipeline.total_duration_ms", total_duration_ms)
    current_span.set_attribute("app.pipeline.llm_call_count", counters.llm_call_count)
    current_span.set_attribute("app.pipeline.tool_call_count", counters.tool_call_count)
    current_span.set_attribute("app.pipeline.input_tokens", counters.input_tokens)
    current_span.set_attribute("app.pipeline.output_tokens", counters.output_tokens)
    current_span.set_attribute("app.pipeline.cache_read_tokens", counters.cache_read_tokens)
    current_span.set_attribute("app.pipeline.recovery_count", recovery_count)
    _set_latency_attribute(
        current_span,
        "app.pipeline.time_to_first_assistant_delta_ms",
        latency_summary.time_to_first_assistant_delta_ms,
    )
    _set_latency_attribute(
        current_span,
        "app.pipeline.time_to_first_assistant_message_ms",
        latency_summary.time_to_first_assistant_message_ms,
    )
    _set_latency_attribute(
        current_span,
        "app.pipeline.time_to_first_tool_call_ms",
        latency_summary.time_to_first_tool_call_ms,
    )
    _set_latency_attribute(
        current_span,
        "app.pipeline.approval_wait_ms",
        latency_summary.approval_wait_ms,
    )
    _set_latency_attribute(
        current_span,
        "app.pipeline.resume_after_approval_ms",
        latency_summary.resume_after_approval_ms,
    )
    _set_latency_attribute(
        current_span,
        "app.pipeline.execution_duration_ms",
        latency_summary.execution_duration_ms,
    )
    if failure_context is not None and failure_context.phase is not None:
        current_span.set_attribute(
            "app.pipeline.failure_phase", failure_context.phase
        )


def _set_latency_attribute(
    span: trace.Span,
    key: str,
    value: int | None,
) -> None:
    if value is not None:
        span.set_attribute(key, value)


def _set_turn_error_span_attributes(
    *,
    error_type: str,
    failure_context: TurnFailureContext | None,
) -> None:
    current_span = trace.get_current_span()
    if not current_span.is_recording():
        return
    current_span.set_attribute("app.pipeline.outcome", "error")
    current_span.set_attribute("app.pipeline.error_type", error_type)
    if failure_context is not None and failure_context.phase is not None:
        current_span.set_attribute(
            "app.pipeline.failure_phase", failure_context.phase
        )


def _current_trace_id() -> str | None:
    """Extract the current OTEL trace ID as a hex string, if recording."""
    span = trace.get_current_span()
    if not span.is_recording():
        return None
    return format(span.get_span_context().trace_id, "032x")


async def _finalize_stream(
    queue: asyncio.Queue[JSONObject],
    turn_ctx: TurnTelemetryContext,
    outcome: str,
    counters: TurnCounters,
    trace_id: str | None,
    *,
    failure_context: TurnFailureContext | None = None,
) -> None:
    """Emit message_end event, record metrics, and shut down the queue."""
    turn_ctx.runtime.mark_first_assistant_delta(counters.first_assistant_delta_at_monotonic)
    turn_ctx.runtime.mark_first_assistant_message(
        counters.first_assistant_message_at_monotonic
    )
    turn_ctx.runtime.mark_first_tool_call(counters.first_tool_call_at_monotonic)
    total_duration_ms = round(
        (time.monotonic() - turn_ctx.turn_started_monotonic) * 1000
    )
    latency_summary = turn_ctx.runtime.latency_summary(
        turn_started_monotonic=turn_ctx.turn_started_monotonic,
        phase_timings=turn_ctx.phase_timings,
    )
    _record_turn_metrics(
        outcome,
        turn_ctx,
        counters,
        total_duration_ms=total_duration_ms,
        latency_summary=latency_summary,
    )
    _set_turn_span_summary_attributes(
        total_duration_ms=total_duration_ms,
        latency_summary=latency_summary,
        counters=counters,
        outcome=outcome,
        failure_context=failure_context,
        recovery_count=len(turn_ctx.runtime.recoveries),
    )
    estimated_cost = estimate_cost(
        turn_ctx.model_id,
        prompt_tokens=counters.input_tokens,
        completion_tokens=counters.output_tokens,
        cached_tokens=counters.cache_read_tokens,
    )
    trace_output = build_turn_output_payload(
        turn_ctx,
        counters,
        outcome=outcome,
        total_duration_ms=total_duration_ms,
        estimated_cost=estimated_cost,
        failure_context=failure_context,
    ).model_dump(by_alias=True)
    latency_payload = latency_summary.model_dump(by_alias=True)
    failure_payload = (
        failure_context.model_dump(by_alias=True) if failure_context is not None else None
    )
    current_span = trace.get_current_span()
    if current_span.is_recording():
        set_langfuse_trace_attributes(
            current_span,
            LangfuseTraceAttributes(output_value=trace_output),
            trace_ctx=LangfuseTraceContext(
                metadata={
                    "outcome": outcome,
                    "total_duration_ms": total_duration_ms,
                    "llm_call_count": counters.llm_call_count,
                    "tool_call_count": counters.tool_call_count,
                    "input_tokens": counters.input_tokens,
                    "output_tokens": counters.output_tokens,
                    "cache_read_tokens": counters.cache_read_tokens,
                    "estimated_cost_usd": estimated_cost,
                    "time_to_first_assistant_delta_ms": latency_summary.time_to_first_assistant_delta_ms,
                    "time_to_first_assistant_message_ms": latency_summary.time_to_first_assistant_message_ms,
                    "time_to_first_tool_call_ms": latency_summary.time_to_first_tool_call_ms,
                    "approval_wait_ms": latency_summary.approval_wait_ms,
                    "resume_after_approval_ms": latency_summary.resume_after_approval_ms,
                    "execution_duration_ms": latency_summary.execution_duration_ms,
                    "recovery_count": len(turn_ctx.runtime.recoveries),
                    "failure_context": failure_payload,
                }
            ),
        )
    logger.info(
        "Pipeline turn summary",
        intent=turn_ctx.intent.value,
        outcome=outcome,
        model_id=turn_ctx.model_id,
        run_kind=turn_ctx.run_kind,
        turn_started_at=turn_ctx.turn_started_at.isoformat(),
        turn_completed_at=datetime.now(UTC).isoformat(),
        total_duration_ms=total_duration_ms,
        llm_call_count=counters.llm_call_count,
        tool_call_count=counters.tool_call_count,
        input_tokens=counters.input_tokens,
        output_tokens=counters.output_tokens,
        cache_read_tokens=counters.cache_read_tokens,
        estimated_cost_usd=estimated_cost,
        latency=latency_payload,
        recovery_count=len(turn_ctx.runtime.recoveries),
        failure_context=failure_payload,
        phases=[snapshot.as_summary() for snapshot in turn_ctx.phase_timings.terminal_history()],
    )
    await queue.put(
        {
            "type": "message_end",
            "data": MessageEndEventData(
                trace_id=trace_id,
                prompt_tokens=counters.input_tokens,
                completion_tokens=counters.output_tokens,
                total_tokens=counters.input_tokens + counters.output_tokens,
                cached_tokens=counters.cache_read_tokens,
                tool_call_count=counters.tool_call_count,
                registered_tool_count=0,
                llm_call_count=counters.llm_call_count,
                estimated_cost_usd=estimated_cost,
                model_id=turn_ctx.model_id,
            ).model_dump(by_alias=True),
        }
    )
    queue.shutdown()


async def _handle_pipeline_error(
    queue: asyncio.Queue[JSONObject],
    error: BaseException,
    *,
    failure_context: TurnFailureContext | None = None,
    intent: str | None = None,
    model_id: str | None = None,
    run_kind: str | None = None,
) -> None:
    """Classify and emit a pipeline-level error event."""
    error_type = type(error).__name__
    metric_attrs = {"error_type": error_type}
    if failure_context is not None and failure_context.phase is not None:
        metric_attrs["phase"] = failure_context.phase
    if intent is not None:
        metric_attrs["intent"] = intent
    if model_id is not None:
        metric_attrs["model"] = model_id
    if run_kind is not None:
        metric_attrs["run_kind"] = run_kind
        metric_attrs["surface"] = _surface_for_run_kind(run_kind)
    pipeline_errors.add(1, metric_attrs)
    _set_turn_error_span_attributes(
        error_type=error_type,
        failure_context=failure_context,
    )
    failure_payload = (
        failure_context.model_dump(by_alias=True) if failure_context is not None else None
    )
    if type(error) is UsageLimitExceeded:
        logger.warning(
            "Agent exceeded token/request budget",
            errorType=error_type,
            failure_context=failure_payload,
        )
        message = (
            "I used too many resources processing your request. Try a simpler or "
            "more specific question."
        )
        current_span = trace.get_current_span()
        if current_span.is_recording():
            set_langfuse_trace_attributes(
                current_span,
                LangfuseTraceAttributes(output_value=message),
                trace_ctx=LangfuseTraceContext(
                    metadata={
                        "error_type": error_type,
                        "failure_context": failure_payload,
                    }
                ),
            )
        await _emit_error(queue, message)
        return

    logger.error(
        "Stream error",
        error=str(error),
        errorType=error_type,
        failure_context=failure_payload,
    )
    message = sanitize_error_for_client(error)
    current_span = trace.get_current_span()
    if current_span.is_recording():
        set_langfuse_trace_attributes(
            current_span,
            LangfuseTraceAttributes(output_value=message),
            trace_ctx=LangfuseTraceContext(
                metadata={
                    "error_type": error_type,
                    "failure_context": failure_payload,
                }
            ),
        )
    await _emit_error(queue, message)


async def _emit_error(queue: asyncio.Queue[JSONObject], message: str) -> None:
    """Push an error event onto the SSE queue."""
    await queue.put(
        {
            "type": "error",
            "data": ErrorEventData(error=message).model_dump(by_alias=True),
        }
    )
