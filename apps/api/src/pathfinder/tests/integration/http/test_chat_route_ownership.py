"""POST /api/v1/chat refuses a conversation owned by another user."""

from __future__ import annotations

import asyncio
from uuid import UUID

import httpx
from fastapi import FastAPI
from procrastinate.testing import InMemoryConnector
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pathfinder.persistence.models import Conversation, Message
from pathfinder.tests.integration.http.conftest import (
    chat_body,
    chat_jobs,
    client_for,
    make_user,
)

_STREAM_TIMEOUT_SECONDS = 15.0


async def _post_chat(client: httpx.AsyncClient, conversation_id: UUID) -> int | None:
    """Return the status code, or None when the route opens an SSE stream."""
    post = asyncio.create_task(
        client.post(
            "/api/v1/chat",
            json=chat_body(conversation_id),
            timeout=60.0,
        ),
    )
    try:
        response = await asyncio.wait_for(
            asyncio.shield(post),
            timeout=_STREAM_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        post.cancel()
        await asyncio.gather(post, return_exceptions=True)
        return None
    return response.status_code


async def _count_messages(
    session_maker: async_sessionmaker[AsyncSession],
    conversation_id: UUID,
) -> int:
    async with session_maker() as session:
        return await session.scalar(
            select(func.count())
            .select_from(Message)
            .where(Message.conversation_id == conversation_id),
        )


async def test_chat_rejects_a_conversation_owned_by_another_user(
    app: FastAPI,
    patch_app_db_engine: None,
    db_session: AsyncSession,
    session_maker: async_sessionmaker[AsyncSession],
    in_memory_jobs: InMemoryConnector,
    signed_in_to_veupathdb: None,
) -> None:
    del patch_app_db_engine, signed_in_to_veupathdb
    owner = await make_user(db_session)
    intruder = await make_user(db_session)
    conversation = Conversation(
        user_id=owner.id,
        site_id="plasmodb",
        name="Owner kinases",
    )
    db_session.add(conversation)
    await db_session.flush()
    await db_session.commit()

    async with client_for(app, intruder.id) as client:
        status = await _post_chat(client, conversation.id)

    assert await _count_messages(session_maker, conversation.id) == 0, (
        "a non-owner's chat POST wrote a message into the owner's conversation"
    )
    assert chat_jobs(in_memory_jobs) == [], (
        "a non-owner's chat POST deferred a turn on the owner's thread"
    )
    assert status == 404, "POST /api/v1/chat must answer 404 for a non-owner; got " + (
        "an open SSE stream" if status is None else str(status)
    )
