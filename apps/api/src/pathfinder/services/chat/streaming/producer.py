"""Pipeline producer — StateChart-driven phase orchestration.

The StateChart governs phase transitions with guards, retry budgets,
and abort capability.  The classifier determines the entry point.
"""

import asyncio
import time
from uuid import uuid4

from opentelemetry import trace
from pydantic_ai.messages import ModelMessage

from pathfinder.ai.models.pricing import estimate_cost
from pathfinder.ai.orchestration.classifier import (
    Intent,
    classify_request,
    classify_request_llm,
)
from pathfinder.ai.orchestration.deps import AgentDeps
from pathfinder.ai.orchestration.observability import get_tracer
from pathfinder.ai.orchestration.pipeline import AgentPipeline, create_pipeline
from pathfinder.domain.strategy.plan import PlanStatus
from pathfinder.platform.errors import sanitize_error_for_client
from pathfinder.platform.event_schemas import (
    AssistantMessageEventData,
    ErrorEventData,
    MessageEndEventData,
    PipelineConfig,
)
from pathfinder.platform.logging import get_logger
from pathfinder.platform.metrics import (
    phase_duration_s,
    pipeline_errors,
    pipeline_runs,
    token_usage,
)
from pathfinder.platform.types import JSONObject
from pathfinder.services.chat.streaming.events import emit_phase_event
from pathfinder.services.chat.streaming.node_streaming import TurnCounters
from pathfinder.services.chat.streaming.phase_runner import (
    PHASE_LIMITS,
    PhaseConfig,
    is_mock_model,
    run_phase,
)
from pathfinder.services.chat.streaming.step_execution import run_execution_phase

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


async def check_plan_approval(
    deps: AgentDeps, queue: asyncio.Queue[JSONObject], pipeline: PipelineConfig,
) -> bool:
    """Check if the plan needs user approval. Returns True to pause the pipeline."""
    active_plan = deps.agent_state.active_plan
    if active_plan is None or active_plan.status != PlanStatus.PRESENTED:
        return False
    if is_mock_model(pipeline.planning.model_id):
        active_plan.status = PlanStatus.APPROVED
        logger.info("Mock mode — auto-approving plan")
        return False
    await emit_phase_event(queue, "planning", "awaiting_approval")
    logger.info("Plan awaiting approval — pausing pipeline")
    return True


async def run_sm_phase(
    sm: AgentPipeline,
    config: PhaseConfig,
    discovery_messages: list[ModelMessage] | None,
    pipeline: PipelineConfig,
) -> tuple[list[ModelMessage] | None, bool]:
    """Execute one StateChart phase and advance the machine.

    Returns ``(discovery_messages, should_break)``.
    """
    phase = config.phase
    if phase == "execution":
        await run_execution_phase(config)
        plan = config.deps.agent_state.active_plan
        if plan is not None and plan.status == PlanStatus.FAILED and sm.should_replan():
            logger.info(
                "Execution failed, replanning",
                attempt=sm.retry_counts.get("execution", 0),
                budget=sm.retry_budget,
            )
            sm.send("replan")
        else:
            sm.send("finish_execution")
    elif phase == "discovery":
        discovery_messages = await run_phase(config)
        sm.send("finish_discovery")
    elif phase == "planning":
        await run_phase(config)
        if await check_plan_approval(config.deps, config.queue, pipeline):
            return discovery_messages, True
        sm.send("submit_draft")
        sm.send("approve")
    elif phase == "verification":
        await run_phase(config)
        sm.send("finish_verification")
    return discovery_messages, False


def _set_phase_span_attributes(
    span: trace.Span,
    phase: str,
    intent: Intent,
    model_id: str,
    deps: AgentDeps,
) -> None:
    """Set app + GenAI semantic convention attributes on a phase span."""
    span.set_attribute("app.phase", phase)
    span.set_attribute("app.intent", intent.value)
    span.set_attribute("gen_ai.agent.name", phase)
    span.set_attribute("gen_ai.operation.name", "invoke_agent")
    span.set_attribute("gen_ai.request.model", model_id)
    graph = deps.strategy_session.get_graph(None)
    if graph is not None:
        span.set_attribute("gen_ai.conversation.id", graph.id)


def _record_turn_metrics(
    intent: Intent,
    outcome: str,
    model_id: str,
    counters: TurnCounters,
) -> None:
    """Record pipeline-level OTEL metrics for a completed turn."""
    attrs = {"intent": intent.value, "outcome": outcome, "model": model_id}
    pipeline_runs.add(1, attrs)
    token_usage.add(counters.input_tokens, {"model": model_id, "type": "input"})
    token_usage.add(counters.output_tokens, {"model": model_id, "type": "output"})
    token_usage.add(counters.cache_read_tokens, {"model": model_id, "type": "cached"})


def _current_trace_id() -> str | None:
    """Extract the current OTEL trace ID as a hex string, if recording."""
    span = trace.get_current_span()
    if not span.is_recording():
        return None
    return format(span.get_span_context().trace_id, "032x")


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
    message_id = str(uuid4())
    counters = TurnCounters()
    sm = create_pipeline()

    current_trace = _current_trace_id()
    tracer = get_tracer()

    intent = await classify_intent(deps, message, pipeline)

    # Fast-forward the StateChart for non-full-pipeline intents.
    if intent == Intent.EDIT_STRATEGY:
        # Skip discovery and planning — go straight to execution.
        sm.send("finish_discovery")
        sm.send("submit_draft")
        sm.send("approve")
    elif intent == Intent.EXTEND_STRATEGY:
        # Skip discovery — searches are already known from existing strategy.
        sm.send("finish_discovery")

    # Use the planning model as the representative for metrics/cost.
    representative_model = pipeline.planning.model_id

    outcome = "completed"
    try:
        discovery_messages: list[ModelMessage] | None = None

        while not sm.is_done:
            phase = sm.current_phase
            logger.info("Pipeline entering phase", phase=phase)
            await emit_phase_event(queue, phase, "started")

            with tracer.start_as_current_span(f"pipeline.{phase}") as phase_span:
                phase_cfg = getattr(pipeline, phase)

                _set_phase_span_attributes(phase_span, phase, intent, phase_cfg.model_id, deps)

                # Discovery and verification get the user's original message.
                # Planning and execution get empty prompts (they work from
                # message_history and dynamic instructions respectively).
                phase_prompt = message if phase in ("discovery", "verification") else ""

                config = PhaseConfig(
                    phase=phase,
                    prompt=phase_prompt,
                    deps=deps,
                    queue=queue,
                    message_id=message_id,
                    counters=counters,
                    model_id=phase_cfg.model_id,
                    reasoning_effort=phase_cfg.reasoning_effort,
                    message_history=discovery_messages if phase == "planning" else None,
                    usage_limits=PHASE_LIMITS.get(phase),
                )

                phase_start = time.monotonic()
                discovery_messages, should_break = await run_sm_phase(
                    sm, config, discovery_messages, pipeline,
                )
                phase_duration_s.record(
                    time.monotonic() - phase_start,
                    {"phase": phase, "intent": intent.value},
                )

            if should_break:
                break

            # QUESTION intent: stop after discovery.
            if intent == Intent.QUESTION and phase == "discovery":
                await emit_phase_event(queue, phase, "completed")
                break

            await emit_phase_event(queue, phase, "completed")

        # Emit the final assistant_message event.
        full_text = "\n\n".join(counters.accumulated_text_parts)
        await queue.put(
            {
                "type": "assistant_message",
                "data": AssistantMessageEventData(
                    message_id=message_id,
                    content=full_text
                    or (
                        ""
                        if counters.saw_assistant_message
                        else "I processed your request."
                    ),
                ).model_dump(by_alias=True),
            }
        )
    except Exception as e:
        outcome = "error"
        pipeline_errors.add(1, {"error_type": type(e).__name__})
        logger.error(
            "Stream error",
            exc_info=True,
            error=str(e),
            errorType=type(e).__name__,
        )
        await queue.put(
            {
                "type": "error",
                "data": ErrorEventData(
                    error=sanitize_error_for_client(e)
                ).model_dump(by_alias=True),
            }
        )
    finally:
        _record_turn_metrics(intent, outcome, representative_model, counters)

        estimated_cost = estimate_cost(
            representative_model,
            prompt_tokens=counters.input_tokens,
            completion_tokens=counters.output_tokens,
            cached_tokens=counters.cache_read_tokens,
        )
        await queue.put(
            {
                "type": "message_end",
                "data": MessageEndEventData(
                    trace_id=current_trace,
                    prompt_tokens=counters.input_tokens,
                    completion_tokens=counters.output_tokens,
                    total_tokens=counters.input_tokens + counters.output_tokens,
                    cached_tokens=counters.cache_read_tokens,
                    tool_call_count=counters.tool_call_count,
                    registered_tool_count=0,
                    llm_call_count=counters.llm_call_count,
                    estimated_cost_usd=estimated_cost,
                    model_id=representative_model,
                ).model_dump(by_alias=True),
            }
        )
        # Signal completion — consumer sees ShutDown on next get().
        queue.shutdown()
