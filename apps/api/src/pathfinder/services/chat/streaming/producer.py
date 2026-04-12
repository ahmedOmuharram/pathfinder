"""Pipeline producer — StateChart-driven phase orchestration."""

import asyncio
import time
from datetime import UTC, datetime
from uuid import uuid4

from pathfinder.ai.orchestration.classifier import (
    Intent,
    classify_request,
    classify_request_llm,
    should_resume_paused_phase,
)
from pathfinder.ai.orchestration.deps import AgentDeps
from pathfinder.ai.orchestration.observability import get_tracer
from pathfinder.ai.orchestration.pipeline import create_pipeline
from pathfinder.domain.strategy.plan import PlanStatus
from pathfinder.platform.event_schemas import PipelineConfig
from pathfinder.platform.logging import get_logger
from pathfinder.platform.types import JSONObject
from pathfinder.services.chat.streaming.turn_execution import (
    TurnExecutionConfig,
    configure_state_machine_for_intent,
    configure_state_machine_for_plan_approval,
    execute_pipeline_turn,
)
from pathfinder.services.chat.streaming.turn_lifecycle import _current_trace_id
from pathfinder.services.chat.streaming.turn_trace_context import (
    _annotate_current_turn_span,
)

logger = get_logger(__name__)


async def classify_intent(
    deps: AgentDeps, message: str, pipeline: PipelineConfig,
) -> Intent:
    """Classify the request and return the resolved intent."""
    graph = deps.strategy_session.graph
    has_pending = (
        deps.agent_state.active_plan is not None
        and deps.agent_state.active_plan.status == PlanStatus.PRESENTED
    )
    classification = classify_request(
        message, graph=graph, has_pending_plan=has_pending,
    )
    planning_model = pipeline.planning.model_id
    if classification is None and planning_model:
        classification = await classify_request_llm(
            message, model_id=planning_model, graph=graph, has_pending_plan=has_pending,
        )
    intent = classification.intent if classification else Intent.NEW_STRATEGY
    logger.info(
        "Request classified",
        intent=intent,
        confidence=classification.confidence if classification else 0.0,
        tier="rule" if classification else "default",
    )
    return intent

async def produce_events(
    deps: AgentDeps,
    message: str,
    queue: asyncio.Queue[JSONObject],
    pipeline: PipelineConfig,
) -> None:
    """Run the agent pipeline driven by the StateChart.

    The StateChart governs phase transitions with guards, retry budgets,
    and abort capability. The classifier determines entry point.
    """
    message_group_id = str(uuid4())
    sm = create_pipeline()
    run_kind = "chat"
    turn_started_at = datetime.now(UTC)
    turn_started_monotonic = time.monotonic()
    current_trace = _current_trace_id()
    tracer = get_tracer()
    intent = await classify_intent(deps, message, pipeline)
    resume_phase = (
        deps.resume_phase
        if deps.resume_phase is not None
        and should_resume_paused_phase(message)
        else None
    )
    _annotate_current_turn_span(
        deps,
        intent=intent,
        run_kind=run_kind,
        message_group_id=message_group_id,
        trace_name=f"chat.{intent.value}",
    )
    if resume_phase is not None:
        logger.info(
            "Resuming paused pipeline phase for follow-up turn",
            resume_phase=resume_phase,
            classified_intent=intent,
        )
    configure_state_machine_for_intent(sm, intent, resume_phase=resume_phase)
    await execute_pipeline_turn(
        TurnExecutionConfig(
            deps=deps,
            queue=queue,
            pipeline=pipeline,
            tracer=tracer,
            intent=intent,
            run_kind=run_kind,
            message_group_id=message_group_id,
            source_message=message,
            history_phases=("discovery", "planning"),
            representative_model=pipeline.planning.model_id,
            current_trace=current_trace,
            turn_started_at=turn_started_at,
            turn_started_monotonic=turn_started_monotonic,
        ),
        sm,
    )


async def produce_plan_approved_events(
    deps: AgentDeps,
    queue: asyncio.Queue[JSONObject],
    pipeline: PipelineConfig,
) -> None:
    """Resume the pipeline from execution after a structured plan approval."""
    message_group_id = str(uuid4())
    sm = create_pipeline()
    run_kind = "plan_approval"
    turn_started_at = datetime.now(UTC)
    turn_started_monotonic = time.monotonic()
    current_trace = _current_trace_id()
    tracer = get_tracer()
    intent = Intent.EDIT_STRATEGY
    _annotate_current_turn_span(
        deps,
        intent=intent,
        run_kind=run_kind,
        message_group_id=message_group_id,
        trace_name="plan_action.approve",
    )
    configure_state_machine_for_plan_approval(sm)
    await execute_pipeline_turn(
        TurnExecutionConfig(
            deps=deps,
            queue=queue,
            pipeline=pipeline,
            tracer=tracer,
            intent=intent,
            run_kind=run_kind,
            message_group_id=message_group_id,
            source_message="",
            history_phases=("planning",),
            representative_model=pipeline.execution.model_id,
            current_trace=current_trace,
            turn_started_at=turn_started_at,
            turn_started_monotonic=turn_started_monotonic,
        ),
        sm,
    )
