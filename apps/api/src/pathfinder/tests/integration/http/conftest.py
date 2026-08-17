"""Shared fixtures and request builders for the HTTP integration tests."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI
from procrastinate.testing import InMemoryConnector
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pathfinder.jobs.app import procrastinate_app
from pathfinder.jobs.tasks import ensure_registered
from pathfinder.persistence.models import User
from pathfinder.platform.security import create_user_token

CHAT_TURN_TASK = "chat_turn:run"


@pytest.fixture
async def db_session(
    session_maker: async_sessionmaker[AsyncSession],
    db_cleaner: None,
) -> AsyncGenerator[AsyncSession]:
    del db_cleaner
    async with session_maker() as session:
        yield session


@pytest.fixture
async def in_memory_jobs() -> AsyncGenerator[InMemoryConnector]:
    """Route deferred jobs to an in-memory connector for the test."""
    original_connector = procrastinate_app.connector
    original_jm_connector = procrastinate_app.job_manager.connector
    connector = InMemoryConnector()
    procrastinate_app.connector = connector
    procrastinate_app.job_manager.connector = connector
    ensure_registered()
    try:
        yield connector
    finally:
        procrastinate_app.connector = original_connector
        procrastinate_app.job_manager.connector = original_jm_connector


async def make_user(session: AsyncSession) -> User:
    user = User(id=uuid4())
    session.add(user)
    await session.flush()
    await session.commit()
    return user


def client_for(app: FastAPI, user_id: UUID) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Requested-With": "XMLHttpRequest"},
        cookies={"pathfinder-auth": create_user_token(user_id)},
    )


def chat_body(conversation_id: UUID) -> dict[str, Any]:
    message_id = str(uuid4())
    return {
        "trigger": "submit-message",
        "id": message_id,
        "messages": [
            {
                "id": message_id,
                "role": "user",
                "parts": [{"type": "text", "text": "list the kinases"}],
            },
        ],
        "conversationId": str(conversation_id),
        "siteId": "plasmodb",
    }


def chat_jobs(connector: InMemoryConnector) -> list[dict[str, Any]]:
    return [j for j in connector.jobs.values() if j["task_name"] == CHAT_TURN_TASK]
