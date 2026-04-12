"""Turn execution helpers for streamed chat pipeline runs."""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from opentelemetry import trace
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.messages import ModelMessage

from pathfinder.ai.orchestration.classifier import Intent
from pathfinder.ai.orchestration.deps import AgentDeps
from pathfinder.ai.orchestration.phase_results import PhaseName
from pathfinder.ai.orchestration.pipeline import AgentPipeline
from pathfinder.platform.errors import AppError
from pathfinder.platform.event_schemas import PipelineConfig
from pathfinder.platform.langfuse.otel import set_langfuse_observation_attributes
from pathfinder.platform.types import JSONObject
from pathfinder.services.chat.streaming.node_streaming import TurnCounters
from pathfinder.services.chat.streaming.phase_driver import run_sm_phase
from pathfinder.services.chat.streaming.phase_runner import (
    PHASE_LIMITS,
    PhaseConfig,
    is_mock_model,
)
from pathfinder.services.chat.streaming.turn_lifecycle import (
    _emit_phase_status,
    _finalize_stream,
    _handle_pipeline_error,
)
from pathfinder.services.chat.streaming.turn_phase_io import (
    emit_phase_assistant_message,
    phase_input_payload,
    phase_output_payload,
    prompt_bundle_for_deps,
    reset_phase_message_buffer,
)
from pathfinder.services.chat.streaming.turn_telemetry import (
    PhaseEventContext,
    PhaseSpanContext,
    PhaseTimingTracker,
    TurnFailureContext,
    TurnRuntimeTelemetry,
    TurnTelemetryContext,
)
from pathfinder.services.chat.streaming.turn_trace_context import (
    _set_phase_span_attributes,
)


@dataclass(frozen=True)
class TurnExecutionConfig:
    """Configuration shared by chat and structured plan-action turn execution."""

    deps: AgentDeps
    queue: asyncio.Queue[JSONObject]
    pipeline: PipelineConfig
    tracer: trace.Tracer
    intent: Intent
    run_kind: str
    message_group_id: str
    source_message: str
    history_phases: tuple[str, ...]
    representative_model: str
    current_trace: str | None
    turn_started_at: datetime
    turn_started_monotonic: float


@dataclass
class TurnLoopState:
    """Mutable state for a single pipeline turn loop."""

    discovery_messages: list[ModelMessage] | None = None
    active_phase: str | None = None
    active_model_id: str | None = None
    active_message_id: str | None = None
    active_terminal_status_emitted: bool = False


def _resume_paused_phase(sm: AgentPipeline, resume_phase: PhaseName) -> None:
    """Advance the state machine to a previously paused phase."""
    if resume_phase == "scoping":
        return
    sm.send("finish_scoping")
    if resume_phase == "discovery":
        return
    sm.send("finish_discovery")
    if resume_phase == "planning":
        return
    sm.send("submit_draft")
    sm.send("approve")
    sm.send("finish_execution")


def configure_state_machine_for_intent(
    sm: AgentPipeline,
    intent: Intent,
    *,
    resume_phase: PhaseName | None = None,
) -> None:
    """Pre-advance the pipeline when the turn intent skips early phases."""
    if resume_phase is not None:
        _resume_paused_phase(sm, resume_phase)
        return
    if intent == Intent.EDIT_STRATEGY:
        sm.send("finish_scoping")
        sm.send("finish_discovery")
        sm.send("submit_draft")
        sm.send("approve")
        return
    if intent == Intent.EXTEND_STRATEGY:
        sm.send("finish_scoping")
        sm.send("finish_discovery")


def configure_state_machine_for_plan_approval(sm: AgentPipeline) -> None:
    """Resume the state machine directly from approved-plan execution."""
    sm.send("finish_scoping")
    sm.send("finish_discovery")
    sm.send("submit_draft")
    sm.send("approve")


def _phase_prompt_for_turn(
    *,
    source_message: str,
    phase: str,
    model_id: str,
) -> str:
    """Return the user prompt that should enter this phase."""
    if not source_message:
        return ""
    if phase in ("scoping", "discovery", "verification"):
        return source_message
    if phase == "planning" and is_mock_model(model_id):
        return source_message
    return ""


def _phase_message_history_for_turn(
    *,
    phase: str,
    discovery_messages: list[ModelMessage] | None,
    history_phases: tuple[str, ...],
) -> list[ModelMessage] | None:
    """Return the history handoff used by a given phase."""
    if phase not in history_phases:
        return None
    return discovery_messages


async def _mark_active_phase_failed(
    queue: asyncio.Queue[JSONObject],
    state: TurnLoopState,
    *,
    intent: Intent,
    run_kind: str,
    phase_timings: PhaseTimingTracker,
    message_group_id: str | None,
) -> None:
    """Emit a failed phase status if the current phase has not ended yet."""
    if (
        state.active_phase is None
        or state.active_model_id is None
        or state.active_terminal_status_emitted
    ):
        return
    await _emit_phase_status(
        queue,
        phase_ctx=PhaseEventContext(
            intent=intent,
            model_id=state.active_model_id,
            run_kind=run_kind,
        ),
        snapshot=phase_timings.snapshot(state.active_phase, "failed"),
        message_id=state.active_message_id,
        message_group_id=message_group_id,
    )


async def _run_pipeline_turn_loop(
    turn_cfg: TurnExecutionConfig,
    sm: AgentPipeline,
    counters: TurnCounters,
    phase_timings: PhaseTimingTracker,
    state: TurnLoopState,
    runtime: TurnRuntimeTelemetry,
) -> None:
    """Run pipeline phases until completion or an intentional pause."""
    while not sm.is_done:
        phase = sm.current_phase
        phase_cfg = getattr(turn_cfg.pipeline, phase)
        phase_message_id = str(uuid4())
        phase_tool_call_count_before = counters.tool_call_count
        reset_phase_message_buffer(counters)
        state.active_phase = phase
        state.active_model_id = phase_cfg.model_id
        state.active_message_id = phase_message_id
        state.active_terminal_status_emitted = False
        phase_event_ctx = PhaseEventContext(
            intent=turn_cfg.intent,
            model_id=phase_cfg.model_id,
            run_kind=turn_cfg.run_kind,
        )
        phase_span_ctx = PhaseSpanContext(
            phase=phase,
            event=phase_event_ctx,
            message_group_id=turn_cfg.message_group_id,
        )
        await _emit_phase_status(
            turn_cfg.queue,
            phase_ctx=phase_event_ctx,
            snapshot=phase_timings.start(phase),
            message_id=phase_message_id,
            message_group_id=turn_cfg.message_group_id,
        )

        with turn_cfg.tracer.start_as_current_span(f"phase.{phase}") as phase_span:
            phase_prompt = _phase_prompt_for_turn(
                source_message=turn_cfg.source_message,
                phase=phase,
                model_id=phase_cfg.model_id,
            )
            message_history = _phase_message_history_for_turn(
                phase=phase,
                discovery_messages=state.discovery_messages,
                history_phases=turn_cfg.history_phases,
            )
            prompt_bundle = prompt_bundle_for_deps(turn_cfg.deps)
            phase_input = phase_input_payload(
                phase=phase,
                phase_prompt=phase_prompt,
                message_history=message_history,
                deps=turn_cfg.deps,
            )
            _set_phase_span_attributes(
                phase_span,
                turn_cfg.deps,
                span_ctx=phase_span_ctx,
                phase_input=phase_input,
                prompt_bundle=prompt_bundle,
            )

            config = PhaseConfig(
                phase=phase,
                prompt=phase_prompt,
                deps=turn_cfg.deps,
                queue=turn_cfg.queue,
                message_id=phase_message_id,
                counters=counters,
                message_group_id=turn_cfg.message_group_id,
                model_id=phase_cfg.model_id,
                reasoning_effort=phase_cfg.reasoning_effort,
                message_history=message_history,
                usage_limits=PHASE_LIMITS.get(phase),
            )

            terminal_history_count_before = len(phase_timings.terminal_history())
            state.discovery_messages, should_break = await run_sm_phase(
                sm,
                config,
                state.discovery_messages,
                phase_timings,
                phase_event_ctx,
                record_recovery=lambda phase, kind, summary, metadata: runtime.record_recovery(
                    phase=phase,
                    kind=kind,
                    summary=summary,
                    metadata=metadata,
                ),
            )
            state.active_terminal_status_emitted = (
                len(phase_timings.terminal_history()) > terminal_history_count_before
            )
            set_langfuse_observation_attributes(
                phase_span,
                output_value=phase_output_payload(
                    turn_cfg.deps,
                    phase,
                    counters=counters,
                    tool_call_count_before=phase_tool_call_count_before,
                    runtime=runtime,
                ),
                metadata={
                    "terminal_status_emitted": state.active_terminal_status_emitted,
                    "tool_calls_used": counters.tool_call_count
                    - phase_tool_call_count_before,
                },
            )

        await emit_phase_assistant_message(
            turn_cfg.queue,
            counters,
            phase=phase,
            message_id=phase_message_id,
            message_group_id=turn_cfg.message_group_id,
            tool_call_count_before=phase_tool_call_count_before,
        )

        if should_break:
            return

        completion_snapshot = phase_timings.snapshot(phase, "completed")
        await _emit_phase_status(
            turn_cfg.queue,
            phase_ctx=phase_event_ctx,
            snapshot=completion_snapshot,
            message_id=phase_message_id,
            message_group_id=turn_cfg.message_group_id,
        )
        state.active_terminal_status_emitted = True


async def execute_pipeline_turn(
    turn_cfg: TurnExecutionConfig,
    sm: AgentPipeline,
) -> None:
    """Run one full pipeline turn including error handling and finalization."""
    counters = TurnCounters()
    phase_timings = PhaseTimingTracker()
    state = TurnLoopState()
    runtime = TurnRuntimeTelemetry(
        approval_wait_ms=(
            turn_cfg.deps.plan_action.approval_wait_ms
            if turn_cfg.deps.plan_action is not None
            else None
        ),
        resume_after_approval_ms=(
            round(
                (
                    turn_cfg.turn_started_at - turn_cfg.deps.plan_action.approved_at
                ).total_seconds()
                * 1000
            )
            if turn_cfg.deps.plan_action is not None
            and turn_cfg.deps.plan_action.approved_at is not None
            else None
        ),
    )
    outcome = "completed"
    failure_context: TurnFailureContext | None = None

    try:
        await _run_pipeline_turn_loop(
            turn_cfg,
            sm,
            counters,
            phase_timings,
            state,
            runtime,
        )
    except (
        UsageLimitExceeded,
        AppError,
        OSError,
        RuntimeError,
        ValueError,
        TypeError,
    ) as error:
        outcome = "error"
        error_type = type(error).__name__
        failure_context = TurnFailureContext(
            error_type=error_type,
            phase=state.active_phase,
            state_machine_phase=sm.current_phase,
            intent=turn_cfg.intent.value,
            run_kind=turn_cfg.run_kind,
            recoverable=False,
            contract_violation=error_type == "MissingPhaseDecisionError",
            recovery_count=len(runtime.recoveries),
        )
        await _mark_active_phase_failed(
            turn_cfg.queue,
            state,
            intent=turn_cfg.intent,
            run_kind=turn_cfg.run_kind,
            phase_timings=phase_timings,
            message_group_id=turn_cfg.message_group_id,
        )
        await _handle_pipeline_error(
            turn_cfg.queue,
            error,
            failure_context=failure_context,
            intent=turn_cfg.intent.value,
            model_id=turn_cfg.representative_model,
            run_kind=turn_cfg.run_kind,
        )
    finally:
        await _finalize_stream(
            turn_cfg.queue,
            TurnTelemetryContext(
                deps=turn_cfg.deps,
                intent=turn_cfg.intent,
                model_id=turn_cfg.representative_model,
                run_kind=turn_cfg.run_kind,
                phase_timings=phase_timings,
                turn_started_at=turn_cfg.turn_started_at,
                turn_started_monotonic=turn_cfg.turn_started_monotonic,
                runtime=runtime,
            ),
            outcome,
            counters,
            turn_cfg.current_trace,
            failure_context=failure_context,
        )
