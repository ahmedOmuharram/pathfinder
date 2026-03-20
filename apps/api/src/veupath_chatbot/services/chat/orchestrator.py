"""Chat orchestration entrypoint (service layer) — CQRS version.

Every event is persisted to Redis the moment it's emitted. The PostgreSQL
projection is updated inline. No accumulation, no finalization step.

AI-layer dependencies (agent factory, model resolver) are injected at
startup via :func:`configure` -- the transport layer calls this once to
wire the concrete implementations. The services layer depends only on
``kani.Kani`` (third-party base class), never on concrete agent types
from ``veupath_chatbot.ai``.
"""

import asyncio
import contextlib
from collections.abc import AsyncIterator, Callable
from uuid import UUID, uuid4

from kani import ChatMessage, ChatRole, Kani
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from veupath_chatbot.ai.agents.factory import EngineConfig
from veupath_chatbot.integrations.veupathdb.factory import get_site
from veupath_chatbot.persistence.models import Stream, StreamProjection
from veupath_chatbot.persistence.repositories import StreamRepository, UserRepository
from veupath_chatbot.persistence.session import async_session_factory
from veupath_chatbot.platform.errors import AppError, InternalError
from veupath_chatbot.platform.events import emit, read_stream_messages
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.redis import get_redis
from veupath_chatbot.platform.types import JSONObject, ModelProvider, ReasoningEffort
from veupath_chatbot.services.chat.mention_context import build_mention_context
from veupath_chatbot.services.chat.streaming import stream_chat
from veupath_chatbot.services.chat.utils import parse_selected_nodes
from veupath_chatbot.transport.http.schemas.sse import ModelSelectedEventData

logger = get_logger(__name__)

# Registry of running chat tasks keyed by operation_id.
# Used to cancel operations from the HTTP layer.
_active_tasks: dict[str, asyncio.Task[None]] = {}

# ── Injected AI-layer dependencies ──────────────────────────────────
# Set once at startup via configure(). Avoids services importing from ai.

_create_agent_holder: dict[str, Callable[..., Kani]] = {}
_resolve_model_id_holder: dict[str, Callable[..., str]] = {}


def configure(
    *,
    create_agent_fn: Callable[..., Kani],
    resolve_model_id_fn: Callable[..., str],
) -> None:
    """Wire AI-layer implementations into the orchestrator.

    Called once at application startup from the composition root.

    Parameters
    ----------
    create_agent_fn:
        Factory that builds a Kani agent for a chat turn.
    resolve_model_id_fn:
        Resolves the effective model ID from overrides and persisted state.
    """
    _create_agent_holder["v"] = create_agent_fn
    _resolve_model_id_holder["v"] = resolve_model_id_fn


async def _ensure_stream(
    stream_repo: StreamRepository,
    *,
    user_id: UUID,
    site_id: str,
    stream_id: UUID | None,
) -> Stream:
    """Ensure a stream exists, creating one if needed."""
    if stream_id:
        stream = await stream_repo.get_by_id(stream_id)
        if stream:
            return stream
        logger.warning("Stream not found; creating new", stream_id=stream_id)
        return await stream_repo.create(
            user_id=user_id, site_id=site_id, stream_id=stream_id
        )
    return await stream_repo.create(user_id=user_id, site_id=site_id)


async def _build_chat_history_from_redis(stream_id: str) -> list[ChatMessage]:
    """Build kani-compatible chat history from Redis stream events."""
    redis = get_redis()
    messages = await read_stream_messages(redis, stream_id)
    history: list[ChatMessage] = []
    for msg in messages:
        role = msg.get("role")
        content = str(msg.get("content", ""))
        if not content:
            continue
        if role == "user":
            _, cleaned = parse_selected_nodes(content)
            history.append(ChatMessage(role=ChatRole.USER, content=cleaned))
        elif role == "assistant":
            history.append(ChatMessage(role=ChatRole.ASSISTANT, content=content))
    return history


async def start_chat_stream(
    *,
    message: str,
    site_id: str,
    strategy_id: UUID | None,
    user_id: UUID,
    user_repo: UserRepository,
    stream_repo: StreamRepository,
    # Per-request model overrides
    provider_override: ModelProvider | None = None,
    model_override: str | None = None,
    reasoning_effort: ReasoningEffort | None = None,
    mentions: list[dict[str, str]] | None = None,
    # Thesis experiment controls
    disable_rag: bool = False,
    disabled_tools: list[str] | None = None,
    temperature: float | None = None,
    seed: int | None = None,
    # Per-model tuning overrides
    context_size: int | None = None,
    response_tokens: int | None = None,
    reasoning_budget: int | None = None,
) -> tuple[str, str]:
    """Start a background chat operation and return its identifiers.

    Returns ``(operation_id, stream_id)`` so the caller can hand them
    to the client. The client subscribes to
    ``GET /operations/{operation_id}/subscribe`` for SSE events.

    Only fast, essential work runs synchronously (user lookup, stream
    resolution, operation registration, user_message emission).
    All heavy lifting is deferred into the background producer.
    """
    await user_repo.get_or_create(user_id)

    stream = await _ensure_stream(
        stream_repo,
        user_id=user_id,
        site_id=site_id,
        stream_id=strategy_id,
    )

    stream_id_str = str(stream.id)
    operation_id = f"op_{uuid4().hex[:12]}"

    # Persist user message to Redis NOW (survives even if producer errors).
    redis = get_redis()
    await emit(
        redis,
        stream_id_str,
        operation_id,
        "user_message",
        {"content": message, "messageId": str(uuid4())},
        session=stream_repo.session,
    )

    # Register the operation in PostgreSQL for client discovery.
    await stream_repo.register_operation(operation_id, stream.id, "chat")

    # Commit before launching the background producer — it creates its own
    # session and must be able to read the Stream/StreamProjection/Operation.
    await stream_repo.session.commit()

    selected_nodes, model_message = parse_selected_nodes(message)

    # Launch the background producer as an asyncio task.
    task = asyncio.create_task(
        _chat_producer(
            stream_id_str=stream_id_str,
            operation_id=operation_id,
            site_id=site_id,
            user_id=user_id,
            model_message=model_message,
            selected_nodes=selected_nodes,
            provider_override=provider_override,
            model_override=model_override,
            reasoning_effort=reasoning_effort,
            mentions=mentions,
            disable_rag=disable_rag,
            disabled_tools=disabled_tools,
            temperature=temperature,
            seed=seed,
            context_size=context_size,
            response_tokens=response_tokens,
            reasoning_budget=reasoning_budget,
        )
    )
    _active_tasks[operation_id] = task
    task.add_done_callback(lambda _: _active_tasks.pop(operation_id, None))

    return operation_id, stream_id_str


async def _build_agent_context(
    *,
    stream_id_str: str,
    site_id: str,
    user_id: UUID,
    model_message: str,
    selected_nodes: JSONObject | None,
    provider_override: ModelProvider | None,
    model_override: str | None,
    reasoning_effort: ReasoningEffort | None,
    mentions: list[dict[str, str]] | None,
    projection: StreamProjection,
    stream_repo: StreamRepository | None = None,
    # Thesis experiment controls
    disable_rag: bool = False,
    temperature: float | None = None,
    seed: int | None = None,
    # Per-model tuning overrides
    context_size: int | None = None,
    response_tokens: int | None = None,
    reasoning_budget: int | None = None,
) -> tuple[Kani, str]:
    """Build the agent and resolve the effective model.

    Handles mention context building, chat history retrieval,
    strategy graph construction, model resolution, and agent creation.

    Returns ``(agent, effective_model_id)``.
    """
    if "v" not in _create_agent_holder or "v" not in _resolve_model_id_holder:
        msg = (
            "Chat orchestrator not configured. "
            "Call services.chat.orchestrator.configure() at startup."
        )
        raise InternalError(detail=msg)

    # Build rich context from @-mentions.
    mentioned_context: str | None = None
    if mentions and stream_repo is not None:
        mentioned_context = await build_mention_context(mentions, stream_repo) or None

    # Build chat history from Redis (not from DB).
    history = await _build_chat_history_from_redis(stream_id_str)

    # Build strategy graph payload from projection.
    strategy_graph_payload: JSONObject = {
        "id": stream_id_str,
        "name": projection.name,
        "plan": projection.plan,
        "steps": projection.steps,
        "rootStepId": projection.root_step_id,
        "recordType": projection.record_type,
        "wdkStrategyId": projection.wdk_strategy_id,
    }

    # Resolve the effective model.
    effective_model: str = _resolve_model_id_holder["v"](
        model_override=model_override,
        persisted_model_id=projection.model_id,
    )

    engine_cfg = EngineConfig(
        provider_override=provider_override,
        model_override=effective_model,
        reasoning_effort=reasoning_effort,
        temperature=temperature,
        seed=seed,
        context_size=context_size,
        reasoning_budget=reasoning_budget,
    )
    agent = _create_agent_holder["v"](
        site_id=site_id,
        user_id=user_id,
        chat_history=history,
        strategy_graph=strategy_graph_payload,
        selected_nodes=selected_nodes,
        engine_config=engine_cfg,
        mentioned_context=mentioned_context,
        disable_rag=disable_rag,
        response_tokens=response_tokens,
    )

    return agent, effective_model


async def _run_stream_loop(
    *,
    redis: Redis,
    session: AsyncSession,
    stream_id_str: str,
    operation_id: str,
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
        except (AppError, ValueError) as exc:
            logger.warning(
                "Failed to build WDK URL",
                site_id=site_id,
                wdk_strategy_id=projection.wdk_strategy_id,
                error=str(exc),
            )

    strategy_payload: JSONObject = {
        "id": stream_id_str,
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
        redis,
        stream_id_str,
        operation_id,
        "message_start",
        {"strategyId": stream_id_str, "strategy": strategy_payload},
        session=session,
    )

    async for event_value in stream_iter:
        if not isinstance(event_value, dict):
            continue
        event_type_raw = event_value.get("type", "")
        event_type = event_type_raw if isinstance(event_type_raw, str) else ""
        event_data_raw = event_value.get("data")
        event_data = event_data_raw if isinstance(event_data_raw, dict) else {}

        await emit(
            redis,
            stream_id_str,
            operation_id,
            event_type,
            event_data,
            session=session,
        )

    await stream_repo.complete_operation(operation_id)


async def _handle_cancellation(
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


async def _handle_error(
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
        {"error": str(error)},
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


async def _chat_producer(
    *,
    stream_id_str: str,
    operation_id: str,
    site_id: str,
    user_id: UUID,
    model_message: str,
    selected_nodes: JSONObject | None,
    provider_override: ModelProvider | None,
    model_override: str | None,
    reasoning_effort: ReasoningEffort | None,
    mentions: list[dict[str, str]] | None,
    # Thesis experiment controls
    disable_rag: bool = False,
    disabled_tools: list[str] | None = None,
    temperature: float | None = None,
    seed: int | None = None,
    # Per-model tuning overrides
    context_size: int | None = None,
    response_tokens: int | None = None,
    reasoning_budget: int | None = None,
) -> None:
    """Background task: run the LLM agent and emit every event to Redis."""
    redis = get_redis()

    async with async_session_factory() as session:
        bg_stream_repo = StreamRepository(session)
        projection = await bg_stream_repo.get_projection(UUID(stream_id_str))

        if not projection:
            await emit(
                redis,
                stream_id_str,
                operation_id,
                "error",
                {"error": "Stream not found"},
            )
            await bg_stream_repo.fail_operation(operation_id)
            await session.commit()
            return

        agent, effective_model = await _build_agent_context(
            stream_id_str=stream_id_str,
            site_id=site_id,
            user_id=user_id,
            model_message=model_message,
            selected_nodes=selected_nodes,
            provider_override=provider_override,
            model_override=model_override,
            reasoning_effort=reasoning_effort,
            mentions=mentions,
            projection=projection,
            stream_repo=bg_stream_repo,
            disable_rag=disable_rag,
            temperature=temperature,
            seed=seed,
            context_size=context_size,
            response_tokens=response_tokens,
            reasoning_budget=reasoning_budget,
        )

        # Remove user-disabled tools from the agent.
        if disabled_tools:
            for tool_name in disabled_tools:
                agent.functions.pop(tool_name, None)

        await emit(
            redis,
            stream_id_str,
            operation_id,
            "model_selected",
            ModelSelectedEventData(modelId=effective_model).model_dump(by_alias=True),
            session=session,
        )

        stream_iter = stream_chat(agent, model_message, model_id=effective_model)

        try:
            await _run_stream_loop(
                redis=redis,
                session=session,
                stream_id_str=stream_id_str,
                operation_id=operation_id,
                site_id=site_id,
                projection=projection,
                stream_iter=stream_iter,
                stream_repo=bg_stream_repo,
            )
        except asyncio.CancelledError:
            await _handle_cancellation(
                redis=redis,
                session=session,
                stream_id_str=stream_id_str,
                operation_id=operation_id,
                stream_repo=bg_stream_repo,
            )
            return
        except (AppError, ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            await _handle_error(
                error=e,
                redis=redis,
                session=session,
                stream_id_str=stream_id_str,
                operation_id=operation_id,
                stream_repo=bg_stream_repo,
            )
            await session.commit()
            return

        await session.commit()


async def cancel_chat_operation(operation_id: str) -> bool:
    """Cancel a running chat operation.

    Returns True if the operation was found and cancelled, False otherwise.

    After calling ``task.cancel()`` we await the task so that its
    CancelledError handler (_handle_cancellation) actually runs.
    Without this, a cancel that arrives before the producer's first
    ``await`` would skip the handler entirely — no ``message_end``
    event, no status update, subscriber hangs forever.
    """
    task = _active_tasks.get(operation_id)
    if task is None:
        return False
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    return True
