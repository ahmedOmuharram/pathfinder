"""Pipeline producer — StateChart-driven phase orchestration.

The StateChart governs phase transitions with guards, retry budgets,
and abort capability.  The classifier determines the entry point.
"""

import asyncio
from uuid import uuid4

from opentelemetry import trace
from pydantic_ai.messages import ModelMessage

from veupath_chatbot.ai.models.pricing import estimate_cost
from veupath_chatbot.ai.orchestration.classifier import (
    Intent,
    classify_request,
    classify_request_llm,
)
from veupath_chatbot.ai.orchestration.deps import AgentDeps
from veupath_chatbot.ai.orchestration.observability import get_tracer
from veupath_chatbot.ai.orchestration.pipeline import AgentPipeline, create_pipeline
from veupath_chatbot.domain.strategy.plan import PlanStatus
from veupath_chatbot.platform.errors import sanitize_error_for_client
from veupath_chatbot.platform.event_schemas import (
    AssistantMessageEventData,
    ErrorEventData,
    MessageEndEventData,
)
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.chat.streaming.events import emit_phase_event
from veupath_chatbot.services.chat.streaming.node_streaming import TurnCounters
from veupath_chatbot.services.chat.streaming.phase_runner import (
    PHASE_LIMITS,
    PhaseConfig,
    is_mock_model,
    run_phase,
)
from veupath_chatbot.services.chat.streaming.step_execution import run_execution_phase

logger = get_logger(__name__)


async def classify_intent(
    deps: AgentDeps, message: str, model_id: str,
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
    if classification is None and model_id:
        classification = await classify_request_llm(
            message, model_id=model_id, graph=graph, has_pending_plan=has_pending,
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
    deps: AgentDeps, queue: asyncio.Queue[JSONObject], model_id: str,
) -> bool:
    """Check if the plan needs user approval. Returns True to pause the pipeline."""
    active_plan = deps.agent_state.active_plan
    if active_plan is None or active_plan.status != PlanStatus.PRESENTED:
        return False
    if is_mock_model(model_id):
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
) -> tuple[list[ModelMessage] | None, bool]:
    """Execute one StateChart phase and advance the machine.

    Returns ``(discovery_messages, should_break)``.
    """
    phase = config.phase
    if phase == "execution":
        await run_execution_phase(config)
        sm.send("finish_execution")
    elif phase == "discovery":
        discovery_messages = await run_phase(config)
        sm.send("finish_discovery")
    elif phase == "planning":
        await run_phase(config)
        if await check_plan_approval(config.deps, config.queue, config.model_id):
            return discovery_messages, True
        sm.send("submit_draft")
        sm.send("approve")
    elif phase == "verification":
        await run_phase(config)
        sm.send("finish_verification")
    return discovery_messages, False


async def produce_events(
    deps: AgentDeps,
    message: str,
    queue: asyncio.Queue[JSONObject],
    model_id: str,
) -> None:
    """Run the agent pipeline driven by the StateChart.

    The StateChart governs phase transitions with guards, retry budgets,
    and abort capability. The classifier determines entry point.
    """
    message_id = str(uuid4())
    counters = TurnCounters()
    sm = create_pipeline()

    current_span = trace.get_current_span()
    current_trace_id: str | None = None
    if current_span.is_recording():
        ctx = current_span.get_span_context()
        current_trace_id = format(ctx.trace_id, "032x")

    tracer = get_tracer()

    intent = await classify_intent(deps, message, model_id)

    # Fast-forward the StateChart for non-full-pipeline intents.
    if intent == Intent.EDIT_STRATEGY:
        # Skip discovery and planning — go straight to execution.
        sm.send("finish_discovery")
        sm.send("submit_draft")
        sm.send("approve")
    elif intent == Intent.EXTEND_STRATEGY:
        # Skip discovery — searches are already known from existing strategy.
        sm.send("finish_discovery")

    try:
        discovery_messages: list[ModelMessage] | None = None

        while not sm.is_done:
            phase = sm.current_phase
            logger.info("Pipeline entering phase", phase=phase)
            await emit_phase_event(queue, phase, "started")

            with tracer.start_as_current_span(f"pipeline.{phase}") as phase_span:
                phase_span.set_attribute("app.phase", phase)
                phase_span.set_attribute("app.intent", intent.value)

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
                    model_id=model_id,
                    message_history=discovery_messages if phase == "planning" else None,
                    usage_limits=PHASE_LIMITS.get(phase),
                )

                discovery_messages, should_break = await run_sm_phase(
                    sm, config, discovery_messages,
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
    except Exception as e:  # pragma: no cover
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
        estimated_cost = estimate_cost(
            model_id,
            prompt_tokens=counters.input_tokens,
            completion_tokens=counters.output_tokens,
            cached_tokens=counters.cache_read_tokens,
        )
        await queue.put(
            {
                "type": "message_end",
                "data": MessageEndEventData(
                    trace_id=current_trace_id,
                    prompt_tokens=counters.input_tokens,
                    completion_tokens=counters.output_tokens,
                    total_tokens=counters.input_tokens + counters.output_tokens,
                    cached_tokens=counters.cache_read_tokens,
                    tool_call_count=counters.tool_call_count,
                    registered_tool_count=0,
                    llm_call_count=counters.llm_call_count,
                    estimated_cost_usd=estimated_cost,
                    model_id=model_id,
                ).model_dump(by_alias=True),
            }
        )
        # Signal completion — consumer sees ShutDown on next get().
        queue.shutdown()
