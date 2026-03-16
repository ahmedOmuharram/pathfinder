"""Workbench chat orchestration entrypoint (service layer).

Mirrors services/chat/orchestrator.py but scoped to experiment-bound
workbench conversations. Streams are keyed by (user_id, experiment_id)
instead of an explicit strategy UUID.

AI-layer dependencies (workbench agent factory, model resolver) are
injected at startup via :func:`configure` — the transport layer calls
this once to wire the concrete implementations so that the services
layer never imports from ``veupath_chatbot.ai``.
"""

import asyncio
from collections.abc import Callable
from uuid import UUID, uuid4

from kani import ChatMessage, ChatRole, Kani

from veupath_chatbot.persistence.repositories.stream import StreamRepository
from veupath_chatbot.persistence.repositories.user import UserRepository
from veupath_chatbot.persistence.session import async_session_factory
from veupath_chatbot.platform.events import emit, read_stream_messages
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.redis import get_redis
from veupath_chatbot.platform.types import JSONObject, ModelProvider, ReasoningEffort
from veupath_chatbot.services.chat.streaming import stream_chat

logger = get_logger(__name__)

# Registry of running workbench chat tasks keyed by operation_id.
# Used to cancel operations from the HTTP layer.
_active_tasks: dict[str, asyncio.Task[None]] = {}

# ── Injected AI-layer dependencies ──────────────────────────────────
# Set once at startup via configure(). Avoids services importing from ai.

_create_workbench_agent: Callable[..., Kani] | None = None
_resolve_effective_model_id: Callable[..., str] | None = None


def configure(
    *,
    create_workbench_agent_fn: Callable[..., Kani],
    resolve_model_id_fn: Callable[..., str],
) -> None:
    """Wire AI-layer implementations into the workbench chat orchestrator.

    Called once at application startup from the composition root.

    Parameters
    ----------
    create_workbench_agent_fn:
        Factory that builds a Kani workbench agent for a chat turn.
    resolve_model_id_fn:
        Resolves the effective model ID from overrides and persisted state.
    """
    global _create_workbench_agent, _resolve_effective_model_id
    _create_workbench_agent = create_workbench_agent_fn
    _resolve_effective_model_id = resolve_model_id_fn


async def start_workbench_chat_stream(
    *,
    message: str,
    site_id: str,
    experiment_id: str,
    user_id: UUID,
    user_repo: UserRepository,
    stream_repo: StreamRepository,
    provider_override: ModelProvider | None = None,
    model_override: str | None = None,
    reasoning_effort: ReasoningEffort | None = None,
) -> tuple[str, str]:
    """Start a background workbench chat operation and return its identifiers.

    Returns ``(operation_id, stream_id)`` so the caller can hand them
    to the client. The client subscribes to
    ``GET /operations/{operation_id}/subscribe`` for SSE events.

    Only fast, essential work runs synchronously (user lookup, stream
    resolution, operation registration, user_message emission).
    All heavy lifting is deferred into the background producer.
    """
    await user_repo.get_or_create(user_id)

    # Find existing stream for this experiment or create a new one.
    stream = await stream_repo.find_by_experiment(user_id, experiment_id)
    if stream is None:
        stream = await stream_repo.create(
            user_id=user_id,
            site_id=site_id,
            experiment_id=experiment_id,
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
    await stream_repo.register_operation(operation_id, stream.id, "workbench_chat")

    # Commit before launching the background producer — it creates its own
    # session and must be able to read the Stream/StreamProjection/Operation.
    await stream_repo.session.commit()

    # Launch the background producer as an asyncio task.
    task = asyncio.create_task(
        _workbench_chat_producer(
            stream_id_str=stream_id_str,
            operation_id=operation_id,
            site_id=site_id,
            experiment_id=experiment_id,
            user_id=user_id,
            message=message,
            provider_override=provider_override,
            model_override=model_override,
            reasoning_effort=reasoning_effort,
        )
    )
    _active_tasks[operation_id] = task
    task.add_done_callback(lambda _: _active_tasks.pop(operation_id, None))

    return operation_id, stream_id_str


async def _build_chat_history_from_redis(
    stream_id_str: str,
) -> list[ChatMessage]:
    """Build kani-compatible chat history from Redis stream events.

    Excludes the last message (the one just emitted for the current turn).
    """
    redis = get_redis()
    messages = await read_stream_messages(redis, stream_id_str)
    history: list[ChatMessage] = []
    for msg in messages[:-1]:  # exclude the message we just emitted
        role = msg.get("role")
        content = str(msg.get("content", ""))
        if not content:
            continue
        if role == "user":
            history.append(ChatMessage(role=ChatRole.USER, content=content))
        elif role == "assistant":
            history.append(ChatMessage(role=ChatRole.ASSISTANT, content=content))
    return history


async def _workbench_chat_producer(
    *,
    stream_id_str: str,
    operation_id: str,
    site_id: str,
    experiment_id: str,
    user_id: UUID,
    message: str,
    provider_override: ModelProvider | None,
    model_override: str | None,
    reasoning_effort: ReasoningEffort | None,
) -> None:
    """Background task: run the workbench LLM agent and emit every event to Redis."""
    if _create_workbench_agent is None or _resolve_effective_model_id is None:
        raise RuntimeError(
            "Workbench chat orchestrator not configured. "
            "Call services.workbench_chat.orchestrator.configure() at startup."
        )

    redis = get_redis()

    async with async_session_factory() as session:
        bg_stream_repo = StreamRepository(session)

        # Build chat history from Redis (not from DB).
        chat_history = await _build_chat_history_from_redis(stream_id_str)

        # Build experiment context for prompt.
        from veupath_chatbot.ai.prompts.workbench_chat import (
            build_workbench_system_prompt,
        )
        from veupath_chatbot.services.experiment.store import get_experiment_store
        from veupath_chatbot.services.experiment.types import to_json

        store = get_experiment_store()
        exp = await store.aget(experiment_id)
        experiment_context: JSONObject = {}
        if exp:
            experiment_context["experimentId"] = exp.id
            experiment_context["status"] = exp.status
            if exp.metrics:
                experiment_context["metrics"] = to_json(exp.metrics)
            if exp.config:
                experiment_context["config"] = to_json(exp.config)

        system_prompt = build_workbench_system_prompt(
            site_id=site_id,
            experiment_context=experiment_context,
        )

        effective_model: str = _resolve_effective_model_id(
            model_override=model_override,
            persisted_model_id=None,
        )

        agent = _create_workbench_agent(
            site_id=site_id,
            user_id=user_id,
            experiment_id=experiment_id,
            chat_history=chat_history,
            system_prompt=system_prompt,
            provider_override=provider_override,
            model_override=effective_model,
            reasoning_effort=reasoning_effort,
        )

        stream_iter = stream_chat(agent, message, model_id=effective_model)

        try:
            await emit(
                redis,
                stream_id_str,
                operation_id,
                "message_start",
                {"experimentId": experiment_id},
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

            await bg_stream_repo.complete_operation(operation_id)

        except asyncio.CancelledError:
            logger.info("Workbench chat producer cancelled", operation_id=operation_id)
            await emit(
                redis,
                stream_id_str,
                operation_id,
                "message_end",
                {},
                session=session,
            )
            await bg_stream_repo.cancel_operation(operation_id)
            await session.commit()
            return

        except Exception as e:
            logger.error(
                "Workbench chat producer error",
                error=str(e),
                exc_info=True,
            )
            await emit(
                redis,
                stream_id_str,
                operation_id,
                "error",
                {"error": str(e)},
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
            await bg_stream_repo.fail_operation(operation_id)

        await session.commit()


async def cancel_workbench_chat_operation(operation_id: str) -> bool:
    """Cancel a running workbench chat operation.

    Returns True if the operation was found and cancelled, False otherwise.
    """
    task = _active_tasks.get(operation_id)
    if task is None:
        return False
    task.cancel()
    return True
