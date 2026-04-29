"""Integration tests for the specialist enter/exit endpoints.

Covers happy paths and the precondition + concurrency refusal paths.
Mirrors the fixture pattern used by ``test_optimize_launcher.py``.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pathfinder.persistence.models import (
    BackgroundTask,
    Conversation,
    ConversationEvent,
    User,
)
from pathfinder.platform.security import create_user_token

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def db_session(
    session_maker: async_sessionmaker[AsyncSession],
    db_cleaner: None,
) -> AsyncGenerator[AsyncSession]:
    del db_cleaner
    async with session_maker() as session:
        yield session


@pytest.fixture
async def seed_user(db_session: AsyncSession) -> User:
    user = User(id=uuid4())
    db_session.add(user)
    await db_session.flush()
    await db_session.commit()
    return user


@pytest.fixture
async def conversation_no_steps(
    db_session: AsyncSession, seed_user: User,
) -> Conversation:
    conv = Conversation(
        id=uuid4(),
        user_id=seed_user.id,
        site_id="plasmodb",
        record_type="transcript",
        name="empty-strategy",
        step_count=0,
        strategy_ast={},
    )
    db_session.add(conv)
    await db_session.flush()
    await db_session.commit()
    return conv


@pytest.fixture
async def conversation_one_step(
    db_session: AsyncSession, seed_user: User,
) -> Conversation:
    conv = Conversation(
        id=uuid4(),
        user_id=seed_user.id,
        site_id="plasmodb",
        record_type="transcript",
        name="single-step",
        step_count=1,
        strategy_ast={
            "recordType": "transcript",
            "steps": [{
                "id": 1,
                "displayName": "Genes by exon count",
                "searchName": "GenesByExonCount",
                "recordClassName": (
                    "TranscriptRecordClasses.TranscriptRecordClass"
                ),
                "estimatedSize": 100,
            }],
        },
    )
    db_session.add(conv)
    await db_session.flush()
    await db_session.commit()
    return conv


@pytest.fixture
async def api_client(
    app: FastAPI,
    patch_app_db_engine: None,
    seed_user: User,
) -> AsyncGenerator[httpx.AsyncClient]:
    del patch_app_db_engine
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"X-Requested-With": "XMLHttpRequest"},
    ) as client:
        client.cookies.set("pathfinder-auth", create_user_token(seed_user.id))
        yield client


@pytest.fixture(autouse=True)
def stub_extraction(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bypass LLM extraction in the context builders so these tests are deterministic."""
    async def _no_criteria(*, recent_turns: object, model_id: object) -> str:
        del recent_turns, model_id
        return ""

    async def _no_focus(
        *, research_question: object, recent_turns: object, model_id: object,
    ) -> object:
        del research_question, recent_turns, model_id
        return None

    monkeypatch.setattr(
        "pathfinder.ai.specialists.context.extract_success_criteria",
        _no_criteria,
    )
    monkeypatch.setattr(
        "pathfinder.ai.specialists.context.extract_biological_focus",
        _no_focus,
    )


async def test_enter_validate_happy_path(
    api_client: httpx.AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    conversation_one_step: Conversation,
) -> None:
    response = await api_client.post(
        f"/api/v1/conversations/{conversation_one_step.id}/specialists/validate/enter",
        json={"arg": ""},
    )
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    assert body["kind"] == "validate"
    assert body["context"]["kind"] == "validate"
    assert body["context"]["strategyName"] == "single-step"

    async with session_maker() as session:
        conv = await session.get(Conversation, conversation_one_step.id)
        assert conv is not None
        assert conv.specialist_mode is not None
        assert conv.specialist_mode["kind"] == "validate"

        events = (
            await session.scalars(
                select(ConversationEvent).where(
                    ConversationEvent.conversation_id
                    == conversation_one_step.id,
                ),
            )
        ).all()
        envelope = next(
            e.chunk for e in events
            if e.chunk.get("type") == "system-message"
            and e.chunk.get("message", {}).get("id") == body["messageId"]
        )
        assert envelope["message"]["parts"][0]["type"] == "data-specialist-entered"


async def test_enter_research_works_without_steps(
    api_client: httpx.AsyncClient,
    conversation_no_steps: Conversation,
) -> None:
    response = await api_client.post(
        f"/api/v1/conversations/{conversation_no_steps.id}/specialists/research/enter",
        json={"arg": "what is PfEMP1?"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["kind"] == "research"
    assert body["context"]["kind"] == "research"
    assert body["context"]["researchQuestion"] == "what is PfEMP1?"


async def test_enter_validate_refused_with_zero_steps(
    api_client: httpx.AsyncClient,
    conversation_no_steps: Conversation,
) -> None:
    response = await api_client.post(
        f"/api/v1/conversations/{conversation_no_steps.id}/specialists/validate/enter",
        json={"arg": ""},
    )
    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "SPECIALIST_PRECONDITION_FAILED"


async def test_enter_refused_when_already_active(
    api_client: httpx.AsyncClient,
    conversation_one_step: Conversation,
) -> None:
    first = await api_client.post(
        f"/api/v1/conversations/{conversation_one_step.id}/specialists/validate/enter",
        json={"arg": ""},
    )
    assert first.status_code == 200, first.text
    second = await api_client.post(
        f"/api/v1/conversations/{conversation_one_step.id}/specialists/research/enter",
        json={"arg": "x"},
    )
    assert second.status_code == 409
    body = second.json()
    assert body["code"] == "SESSION_CONFLICT"


async def test_exit_clears_specialist_mode(
    api_client: httpx.AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    conversation_one_step: Conversation,
) -> None:
    enter = await api_client.post(
        f"/api/v1/conversations/{conversation_one_step.id}/specialists/validate/enter",
        json={"arg": ""},
    )
    assert enter.status_code == 200
    response = await api_client.post(
        f"/api/v1/conversations/{conversation_one_step.id}/specialists/exit",
    )
    assert response.status_code == 200
    body = response.json()
    assert body["cleared"] is True

    async with session_maker() as session:
        conv = await session.get(Conversation, conversation_one_step.id)
        assert conv is not None
        assert conv.specialist_mode is None


async def test_exit_idempotent_when_no_specialist_mode(
    api_client: httpx.AsyncClient,
    conversation_one_step: Conversation,
) -> None:
    response = await api_client.post(
        f"/api/v1/conversations/{conversation_one_step.id}/specialists/exit",
    )
    assert response.status_code == 200
    body = response.json()
    assert body["cleared"] is False
    assert body["messageId"] is None


async def test_patch_state_swaps_model_id(
    api_client: httpx.AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    conversation_one_step: Conversation,
) -> None:
    enter = await api_client.post(
        f"/api/v1/conversations/{conversation_one_step.id}/specialists/validate/enter",
        json={"arg": ""},
    )
    assert enter.status_code == 200
    initial = enter.json()["modelId"]

    response = await api_client.patch(
        f"/api/v1/conversations/{conversation_one_step.id}/specialists/state",
        json={"modelId": "anthropic:claude-haiku-4-5"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["modelId"] == "anthropic:claude-haiku-4-5"
    assert body["modelId"] != initial

    async with session_maker() as session:
        conv = await session.get(Conversation, conversation_one_step.id)
        assert conv is not None
        assert conv.specialist_mode is not None
        assert conv.specialist_mode["modelId"] == "anthropic:claude-haiku-4-5"


async def test_patch_state_rejects_unknown_model(
    api_client: httpx.AsyncClient,
    conversation_one_step: Conversation,
) -> None:
    enter = await api_client.post(
        f"/api/v1/conversations/{conversation_one_step.id}/specialists/validate/enter",
        json={"arg": ""},
    )
    assert enter.status_code == 200

    response = await api_client.patch(
        f"/api/v1/conversations/{conversation_one_step.id}/specialists/state",
        json={"modelId": "made-up:not-a-real-model"},
    )
    assert response.status_code in (400, 422)


async def test_patch_state_refused_when_no_specialist(
    api_client: httpx.AsyncClient,
    conversation_one_step: Conversation,
) -> None:
    response = await api_client.patch(
        f"/api/v1/conversations/{conversation_one_step.id}/specialists/state",
        json={"modelId": "anthropic:claude-haiku-4-5"},
    )
    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "SPECIALIST_PRECONDITION_FAILED"


async def test_exit_refused_while_durable_task_inflight(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    conversation_one_step: Conversation,
) -> None:
    enter = await api_client.post(
        f"/api/v1/conversations/{conversation_one_step.id}/specialists/validate/enter",
        json={"arg": ""},
    )
    assert enter.status_code == 200, enter.text

    inflight_task = BackgroundTask(
        id=uuid4(),
        conversation_id=conversation_one_step.id,
        user_id=conversation_one_step.user_id,
        tool_name="run_control_tests_on_step",
        status="running",
        args={"step_id": 1},
        estimated_duration_seconds=120,
        created_at=datetime.now(UTC),
    )
    db_session.add(inflight_task)
    await db_session.flush()
    await db_session.commit()

    response = await api_client.post(
        f"/api/v1/conversations/{conversation_one_step.id}/specialists/exit",
    )
    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "SESSION_CONFLICT"
