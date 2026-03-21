"""Tests for operation lifecycle edge cases — conversation loading bugs."""

import contextlib
import inspect
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from veupath_chatbot.persistence.models import Operation
from veupath_chatbot.persistence.repositories.stream import StreamRepository
from veupath_chatbot.platform.redis import get_redis, init_redis
from veupath_chatbot.services.chat.orchestrator import _chat_producer, _TurnRequest
from veupath_chatbot.services.chat.types import ChatTurnConfig


async def _setup_stream_and_operation(
    stream_repo: StreamRepository,
    user_id: UUID,
    session: AsyncSession,
) -> tuple[UUID, str]:
    """Create a stream + projection + active operation, commit, return IDs."""
    stream = await stream_repo.create(user_id, "plasmodb")
    operation_id = f"op_{uuid4().hex[:12]}"
    await stream_repo.register_operation(operation_id, stream.id, "chat")
    await session.commit()
    return stream.id, operation_id


def _make_turn(stream_id: UUID, user_id: UUID) -> _TurnRequest:
    return _TurnRequest(
        stream_id_str=str(stream_id),
        site_id="plasmodb",
        user_id=user_id,
        model_message="test message",
        selected_nodes=None,
    )


async def _get_operation_status(
    session: AsyncSession, operation_id: str
) -> str | None:
    session.expire_all()
    result = await session.execute(
        select(Operation.status).where(Operation.operation_id == operation_id)
    )
    return result.scalar_one_or_none()


def _patch_producer_to_raise(exc: Exception):
    return (
        patch(
            "veupath_chatbot.services.chat.orchestrator._build_agent_context",
            new_callable=AsyncMock,
            return_value=(MagicMock(), "test-model"),
        ),
        patch(
            "veupath_chatbot.services.chat.orchestrator.stream_chat",
            return_value=MagicMock(),
        ),
        patch(
            "veupath_chatbot.services.chat.orchestrator._run_stream_loop",
            new_callable=AsyncMock,
            side_effect=exc,
        ),
    )


@pytest.mark.asyncio
async def test_producer_fails_operation_on_attribute_error(
    db_session: AsyncSession,
    stream_repo: StreamRepository,
    user_id: UUID,
    patch_app_db_engine: None,
) -> None:
    """AttributeError in the stream loop must fail the operation."""
    stream_id, operation_id = await _setup_stream_and_operation(
        stream_repo, user_id, db_session,
    )

    p1, p2, p3 = _patch_producer_to_raise(
        AttributeError("simulated: NoneType has no attr 'foo'"),
    )
    with p1, p2, p3, contextlib.suppress(AttributeError):
        await _chat_producer(
            operation_id=operation_id,
            turn=_make_turn(stream_id, user_id),
            config=ChatTurnConfig(),
        )

    status = await _get_operation_status(db_session, operation_id)
    assert status == "failed"


@pytest.mark.asyncio
async def test_producer_fails_operation_on_index_error(
    db_session: AsyncSession,
    stream_repo: StreamRepository,
    user_id: UUID,
    patch_app_db_engine: None,
) -> None:
    """IndexError in the stream loop must fail the operation."""
    stream_id, operation_id = await _setup_stream_and_operation(
        stream_repo, user_id, db_session,
    )

    p1, p2, p3 = _patch_producer_to_raise(IndexError("list index out of range"))
    with p1, p2, p3, contextlib.suppress(IndexError):
        await _chat_producer(
            operation_id=operation_id,
            turn=_make_turn(stream_id, user_id),
            config=ChatTurnConfig(),
        )

    status = await _get_operation_status(db_session, operation_id)
    assert status == "failed"


@pytest.mark.asyncio
async def test_producer_emits_message_end_on_unexpected_error(
    db_session: AsyncSession,
    stream_repo: StreamRepository,
    user_id: UUID,
    patch_app_db_engine: None,
) -> None:
    """Unexpected exceptions must emit message_end so SSE subscribers close."""
    stream_id, operation_id = await _setup_stream_and_operation(
        stream_repo, user_id, db_session,
    )

    p1, p2, p3 = _patch_producer_to_raise(AttributeError("simulated"))
    with p1, p2, p3, contextlib.suppress(AttributeError):
        await _chat_producer(
            operation_id=operation_id,
            turn=_make_turn(stream_id, user_id),
            config=ChatTurnConfig(),
        )

    redis = get_redis()
    entries = await redis.xrange(f"stream:{stream_id}")
    event_types = [
        fields.get(b"type", b"").decode()
        for _, fields in entries
        if fields.get(b"type", b"").decode()
    ]
    assert "message_end" in event_types


@pytest.mark.asyncio
async def test_stale_active_operation_persists(
    db_session: AsyncSession,
    stream_repo: StreamRepository,
    user_id: UUID,
) -> None:
    """An orphaned active operation with no producer stays active."""
    stream = await stream_repo.create(user_id, "plasmodb")
    operation_id = f"op_{uuid4().hex[:12]}"
    await stream_repo.register_operation(operation_id, stream.id, "chat")
    await db_session.commit()

    status = await _get_operation_status(db_session, operation_id)
    assert status == "active"


def test_redis_client_has_socket_timeout() -> None:
    """init_redis() must configure socket timeouts."""
    source = inspect.getsource(init_redis)
    assert "socket_timeout" in source
    assert "socket_connect_timeout" in source
