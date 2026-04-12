"""Background chat producer — runs the LLM pipeline and emits events.

Houses the asyncio task that drives a single chat turn: resolves the agent
dependencies, streams events from the pipeline to Redis/PostgreSQL, and
handles cancellation and error recovery.
"""

import asyncio
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from pathfinder.ai.orchestration.observability import (
    annotate_span_with_observability_identity,
    get_observability_identity,
    get_tracer,
)
from pathfinder.domain.strategy.plan import StrategyPlan
from pathfinder.domain.strategy.plan_payload import StrategyPlanPayload
from pathfinder.integrations.veupathdb.factory import get_site
from pathfinder.persistence.models import StreamProjection
from pathfinder.persistence.repositories import PlanRepository, StreamRepository
from pathfinder.persistence.session import async_session_factory
from pathfinder.platform.context import operation_id_ctx, stream_id_ctx
from pathfinder.platform.errors import (
    AppError,
    sanitize_error_for_client,
)
from pathfinder.platform.event_schemas import (
    ErrorEventData,
    MessageStartEventData,
    ModelSelectedEventData,
    PipelineConfig,
)
from pathfinder.platform.events import emit
from pathfinder.platform.langfuse.otel import (
    LangfuseTraceAttributes,
    LangfuseTraceContext,
    set_langfuse_trace_attributes,
)
from pathfinder.platform.logging import get_logger
from pathfinder.platform.redis import get_redis
from pathfinder.platform.types import JSONObject
from pathfinder.services.chat.deps import build_agent_deps
from pathfinder.services.chat.streaming import (
    stream_pipeline,
    stream_pipeline_after_plan_approval,
)
from pathfinder.services.chat.types import (
    ChatTurnConfig,
    TurnIdentity,
    turn_metadata_trace_fields,
)

logger = get_logger(__name__)


def _trace_input_payload(
    turn: TurnIdentity,
    config: ChatTurnConfig,
) -> str | JSONObject:
    """Return the high-level trace input for Langfuse."""
    if config.plan_action is None:
        payload: JSONObject = {
            "kind": "chat_message",
            "siteId": turn.site_id,
            "streamId": turn.stream_id_str,
            "message": turn.model_message,
        }
        if config.metadata:
            payload["metadata"] = config.metadata
        return payload
    return {
        "kind": "plan_action",
        "siteId": turn.site_id,
        "streamId": turn.stream_id_str,
        "planAction": {
            "action": config.plan_action.action,
            "planId": config.plan_action.plan_id,
            "sourceTraceId": config.plan_action.source_trace_id,
            "sourceMessageGroupId": config.plan_action.source_message_group_id,
            "source": config.plan_action.source,
            "answeredQuestionIds": config.plan_action.answered_question_ids,
            "editedParams": config.plan_action.edited_params,
            "presentedAt": (
                config.plan_action.presented_at.isoformat()
                if config.plan_action.presented_at is not None
                else None
            ),
            "approvedAt": (
                config.plan_action.approved_at.isoformat()
                if config.plan_action.approved_at is not None
                else None
            ),
            "approvalWaitMs": config.plan_action.approval_wait_ms,
        },
    }


@dataclass
class EmitContext:
    """Context for emitting events to a Redis stream."""

    redis: Redis
    session: AsyncSession
    stream_id_str: str
    operation_id: str


async def _persist_plan_event(
    *,
    event_type: str,
    event_data: JSONObject,
    plan_repo: PlanRepository,
    stream_id_str: str,
    operation_id: str,
) -> None:
    """Persist plan-related SSE events into the plan repository."""
    stream_uuid = UUID(stream_id_str)

    if event_type == "plan_presented":
        plan_payload = event_data.get("plan")
        if not isinstance(plan_payload, dict):
            return
        try:
            plan = StrategyPlan.model_validate(plan_payload)
        except (TypeError, ValueError):
            logger.warning(
                "Failed to persist presented plan",
                stream_id=stream_id_str,
                operation_id=operation_id,
            )
            return
        await plan_repo.save_plan(plan, stream_uuid)
        return

    if event_type != "plan_updated":
        return

    plan_updates = event_data.get("updates")
    if not isinstance(plan_updates, dict):
        return

    existing = await plan_repo.get_latest_plan(stream_uuid)
    merged_payload = (
        {
            **existing.model_dump(by_alias=True, mode="json"),
            **plan_updates,
        }
        if existing is not None
        else plan_updates
    )
    try:
        plan = StrategyPlan.model_validate(merged_payload)
    except (TypeError, ValueError):
        logger.warning(
            "Failed to persist plan update",
            stream_id=stream_id_str,
            operation_id=operation_id,
        )
        return
    await plan_repo.save_plan(plan, stream_uuid)


async def run_stream_loop(
    emit_ctx: EmitContext,
    *,
    site_id: str,
    projection: StreamProjection,
    stream_iter: AsyncIterator[JSONObject],
    stream_repo: StreamRepository,
) -> None:
    """Emit message_start, iterate the stream, and mark completion.

    Emits a ``message_start`` event with strategy context, then forwards
    every event from the stream iterator to Redis/PostgreSQL via ``emit()``.
    """
    # Extract description from plan metadata when available.
    try:
        plan_payload = StrategyPlanPayload.model_validate(projection.plan) if projection.plan else None
    except (ValueError, TypeError):
        plan_payload = None
    description = (
        plan_payload.metadata.get("description")
        if plan_payload and plan_payload.metadata
        else None
    )

    # Compute WDK URL when we have a strategy ID and site.
    wdk_url: str | None = None
    if projection.wdk_strategy_id is not None and site_id:
        try:
            site = get_site(site_id)
            wdk_url = site.strategy_url(projection.wdk_strategy_id)
        except AppError as exc:
            logger.warning(
                "Failed to build WDK URL",
                site_id=site_id,
                wdk_strategy_id=projection.wdk_strategy_id,
                error=str(exc),
            )

    strategy_payload: JSONObject = {
        "id": emit_ctx.stream_id_str,
        "name": projection.name,
        "title": projection.name,
        "description": description,
        "siteId": site_id,
        "recordType": projection.record_type,
        "wdkStrategyId": projection.wdk_strategy_id,
        "isSaved": projection.is_saved,
        "wdkUrl": wdk_url,
    }
    await emit(
        emit_ctx.redis,
        emit_ctx.stream_id_str,
        emit_ctx.operation_id,
        "message_start",
        MessageStartEventData(
            strategy_id=emit_ctx.stream_id_str, strategy=strategy_payload
        ).model_dump(by_alias=True, exclude_none=True),
        session=emit_ctx.session,
    )

    plan_repo = PlanRepository(emit_ctx.session)
    async for event_value in stream_iter:
        if not isinstance(event_value, dict):
            continue
        event_type_raw = event_value.get("type", "")
        event_type = event_type_raw if isinstance(event_type_raw, str) else ""
        event_data_raw = event_value.get("data")
        event_data = event_data_raw if isinstance(event_data_raw, dict) else {}

        await emit(
            emit_ctx.redis,
            emit_ctx.stream_id_str,
            emit_ctx.operation_id,
            event_type,
            event_data,
            session=emit_ctx.session,
        )
        await _persist_plan_event(
            event_type=event_type,
            event_data=event_data,
            plan_repo=plan_repo,
            stream_id_str=emit_ctx.stream_id_str,
            operation_id=emit_ctx.operation_id,
        )

    await stream_repo.complete_operation(emit_ctx.operation_id)


async def handle_cancellation(
    *,
    redis: Redis,
    session: AsyncSession,
    stream_id_str: str,
    operation_id: str,
    stream_repo: StreamRepository,
) -> None:
    """Handle task cancellation: emit message_end and update operation status."""
    logger.info("Chat producer cancelled", operation_id=operation_id)
    await emit(
        redis,
        stream_id_str,
        operation_id,
        "message_end",
        {},
        session=session,
    )
    await stream_repo.cancel_operation(operation_id)
    await session.commit()


async def handle_error(
    *,
    error: Exception,
    redis: Redis,
    session: AsyncSession,
    stream_id_str: str,
    operation_id: str,
    stream_repo: StreamRepository,
) -> None:
    """Handle producer errors: log, emit error + message_end, fail operation."""
    logger.error("Chat producer error", error=str(error))
    await session.rollback()
    await emit(
        redis,
        stream_id_str,
        operation_id,
        "error",
        ErrorEventData(error=sanitize_error_for_client(error)).model_dump(
            by_alias=True, exclude_none=True
        ),
        session=session,
    )
    await emit(
        redis,
        stream_id_str,
        operation_id,
        "message_end",
        {},
        session=session,
    )
    await stream_repo.fail_operation(operation_id)


async def chat_producer(
    *,
    operation_id: str,
    turn: TurnIdentity,
    config: ChatTurnConfig,
    resolve_pipeline_fn: Callable[..., PipelineConfig],
) -> None:
    """Background task: run the LLM agent and emit every event to Redis."""
    redis = get_redis()

    async with async_session_factory() as session:
        bg_stream_repo = StreamRepository(session)
        projection = await bg_stream_repo.get_projection(UUID(turn.stream_id_str))

        if not projection:
            await emit(
                redis,
                turn.stream_id_str,
                operation_id,
                "error",
                ErrorEventData(error="Stream not found").model_dump(
                    by_alias=True, exclude_none=True
                ),
            )
            await bg_stream_repo.fail_operation(operation_id)
            await session.commit()
            return

        tracer = get_tracer()
        try:
            with tracer.start_as_current_span("chat.turn") as span:
                observability_identity = get_observability_identity()
                turn_kind = "plan_action" if config.plan_action is not None else "chat"
                stream_id_ctx.set(turn.stream_id_str)
                operation_id_ctx.set(operation_id)
                annotate_span_with_observability_identity(span)
                span.set_attribute("app.stream_id", turn.stream_id_str)
                span.set_attribute("app.operation_id", operation_id)
                span.set_attribute("app.site_id", turn.site_id)
                span.set_attribute("app.user_id", str(turn.user_id))
                span.set_attribute("app.turn_kind", turn_kind)
                span.set_attribute("app.turn_id", operation_id)
                root_trace_context = LangfuseTraceContext(
                    user_id=str(turn.user_id),
                    session_id=turn.stream_id_str,
                    tags=(turn.site_id, turn_kind),
                    metadata={
                        "service_name": observability_identity["service.name"],
                        "service_version": observability_identity["service.version"],
                        "deployment_environment": observability_identity[
                            "deployment.environment.name"
                        ],
                        "site_id": turn.site_id,
                        "stream_id": turn.stream_id_str,
                        "operation_id": operation_id,
                        "turn_id": operation_id,
                        "turn_kind": turn_kind,
                        **turn_metadata_trace_fields(config.metadata),
                        "plan_action": (
                            config.plan_action.action
                            if config.plan_action is not None
                            else None
                        ),
                        "plan_id": (
                            config.plan_action.plan_id
                            if config.plan_action is not None
                            else None
                        ),
                    },
                    release=observability_identity["service.version"],
                    environment=observability_identity[
                        "deployment.environment.name"
                    ],
                )
                set_langfuse_trace_attributes(
                    span,
                    LangfuseTraceAttributes(
                        as_root=True,
                        name=(
                            f"plan_action.{config.plan_action.action}"
                            if config.plan_action is not None
                            else "chat.turn"
                        ),
                        input_value=_trace_input_payload(turn, config),
                    ),
                    trace_ctx=root_trace_context,
                )

                deps, effective_pipeline = await build_agent_deps(
                    turn=turn,
                    projection=projection,
                    config=config,
                    resolve_pipeline_fn=resolve_pipeline_fn,
                    stream_repo=bg_stream_repo,
                )
                set_langfuse_trace_attributes(
                    span,
                    LangfuseTraceAttributes(),
                    trace_ctx=LangfuseTraceContext(
                        metadata={
                            "record_type": projection.record_type,
                            "wdk_strategy_id": projection.wdk_strategy_id,
                            "scoping_model": effective_pipeline.scoping.model_id,
                            "discovery_model": effective_pipeline.discovery.model_id,
                            "planning_model": effective_pipeline.planning.model_id,
                            "execution_model": effective_pipeline.execution.model_id,
                            "verification_model": effective_pipeline.verification.model_id,
                        }
                    ),
                )

                await emit(
                    redis,
                    turn.stream_id_str,
                    operation_id,
                    "model_selected",
                    ModelSelectedEventData(pipeline=effective_pipeline).model_dump(
                        by_alias=True, exclude_none=True
                    ),
                    session=session,
                )

                stream_iter = (
                    stream_pipeline_after_plan_approval(
                        deps,
                        pipeline=effective_pipeline,
                    )
                    if config.plan_action is not None
                    else stream_pipeline(
                        deps,
                        turn.model_message,
                        pipeline=effective_pipeline,
                    )
                )
                emit_ctx = EmitContext(
                    redis=redis,
                    session=session,
                    stream_id_str=turn.stream_id_str,
                    operation_id=operation_id,
                )

                await run_stream_loop(
                    emit_ctx,
                    site_id=turn.site_id,
                    projection=projection,
                    stream_iter=stream_iter,
                    stream_repo=bg_stream_repo,
                )
        except asyncio.CancelledError:
            await handle_cancellation(
                redis=redis,
                session=session,
                stream_id_str=turn.stream_id_str,
                operation_id=operation_id,
                stream_repo=bg_stream_repo,
            )
            return
        except BaseException as e:
            if not isinstance(e, Exception):
                raise
            await handle_error(
                error=e,
                redis=redis,
                session=session,
                stream_id_str=turn.stream_id_str,
                operation_id=operation_id,
                stream_repo=bg_stream_repo,
            )
            await session.commit()
            return

        await session.commit()
