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

from veupath_chatbot.ai.orchestration.observability import get_tracer
from veupath_chatbot.integrations.veupathdb.factory import get_site
from veupath_chatbot.persistence.models import StreamProjection
from veupath_chatbot.persistence.repositories import StreamRepository
from veupath_chatbot.persistence.session import async_session_factory
from veupath_chatbot.platform.context import operation_id_ctx, stream_id_ctx
from veupath_chatbot.platform.errors import (
    AppError,
    sanitize_error_for_client,
)
from veupath_chatbot.platform.event_schemas import (
    ErrorEventData,
    MessageStartEventData,
    ModelSelectedEventData,
    PipelineConfig,
)
from veupath_chatbot.platform.events import emit
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.redis import get_redis
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.chat.deps import build_agent_deps
from veupath_chatbot.services.chat.streaming import stream_pipeline
from veupath_chatbot.services.chat.types import ChatTurnConfig, TurnIdentity

logger = get_logger(__name__)


@dataclass
class EmitContext:
    """Context for emitting events to a Redis stream."""

    redis: Redis
    session: AsyncSession
    stream_id_str: str
    operation_id: str


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
    plan = projection.plan if isinstance(projection.plan, dict) else {}
    meta = plan.get("metadata") if isinstance(plan, dict) else None
    description = meta.get("description") if isinstance(meta, dict) else None

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
        with tracer.start_as_current_span("chat.turn") as span:
            stream_id_ctx.set(turn.stream_id_str)
            operation_id_ctx.set(operation_id)
            span.set_attribute("app.stream_id", turn.stream_id_str)
            span.set_attribute("app.operation_id", operation_id)
            span.set_attribute("app.site_id", turn.site_id)
            span.set_attribute("app.user_id", str(turn.user_id))
            span.set_attribute("langfuse.session.id", turn.stream_id_str)
            span.set_attribute("langfuse.user.id", str(turn.user_id))
            span.set_attribute("langfuse.tags", [turn.site_id])

            deps, effective_pipeline = await build_agent_deps(
                turn=turn,
                projection=projection,
                config=config,
                resolve_pipeline_fn=resolve_pipeline_fn,
                stream_repo=bg_stream_repo,
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

            stream_iter = stream_pipeline(
                deps, turn.model_message, pipeline=effective_pipeline
            )
            emit_ctx = EmitContext(
                redis=redis,
                session=session,
                stream_id_str=turn.stream_id_str,
                operation_id=operation_id,
            )

            try:
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
            except Exception as e:  # noqa: BLE001
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
