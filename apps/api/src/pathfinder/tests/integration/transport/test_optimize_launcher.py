from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pathfinder.domain.search import SearchContext
from pathfinder.domain.strategy.validation import StepValidation
from pathfinder.integrations.veupathdb.wdk_models import (
    WDKSearch,
    WDKSearchResponse,
)
from pathfinder.integrations.veupathdb.wdk_parameters import (
    WDKNumberParam,
)
from pathfinder.jobs.app import procrastinate_app
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
async def conversation_with_step(
    db_session: AsyncSession, seed_user: User,
) -> Conversation:
    """Conversation carrying a single-step strategy whose WDK id is 42."""
    local_step_id = "step-local-1"
    strategy_ast = {
        "recordType": "transcript",
        "root": {
            "id": local_step_id,
            "searchName": "GenesByExonCount",
            "parameters": {},
        },
        "wdkStepIds": {local_step_id: 42},
    }
    conv = Conversation(
        id=uuid4(),
        user_id=seed_user.id,
        site_id="plasmodb",
        record_type="transcript",
        name="opt-test",
        step_count=1,
        strategy_ast=strategy_ast,
        wdk_strategy_id=12345,
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


@pytest.fixture
def patch_discovery(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub ``DiscoveryService.get_search_details`` with a numeric param spec.

    The launcher needs ``min`` / ``max`` / ``increment`` to derive a
    numeric ``ParameterSpec`` for the sweep, so the stubbed param carries
    those fields explicitly.
    """
    param = WDKNumberParam(
        name="exon_count",
        display_name="Exon count",
        is_number=True,
        min=1,
        max=20,
        increment=1,
    )
    response = WDKSearchResponse(
        search_data=WDKSearch(
            url_segment="GenesByExonCount",
            display_name="Genes by exon count",
            parameters=[param],
            param_names=[param.name],
        ),
        validation=StepValidation(),
    )

    async def _fake(
        self: object,
        ctx: SearchContext,
        *,
        expand_params: bool = True,
    ) -> WDKSearchResponse:
        del self, ctx, expand_params
        return response

    monkeypatch.setattr(
        "pathfinder.integrations.veupathdb.discovery_service."
        "DiscoveryService.get_search_details",
        _fake,
    )


@pytest.fixture
async def procrastinate_open(
    patch_app_db_engine: None,
) -> AsyncGenerator[None]:
    """Open the procrastinate app's connector for the test duration.

    ``defer_async`` fails outside an open connector. Production opens it
    in the FastAPI lifespan; the ASGI test transport skips lifespan, so
    we open it explicitly here.
    """
    del patch_app_db_engine
    async with procrastinate_app.open_async():
        yield


async def test_launch_optimize_happy_path(
    api_client: httpx.AsyncClient,
    session_maker: async_sessionmaker[AsyncSession],
    conversation_with_step: Conversation,
    patch_discovery: None,
    procrastinate_open: None,
) -> None:
    del patch_discovery, procrastinate_open
    response = await api_client.post(
        f"/api/v1/conversations/{conversation_with_step.id}/launchers/optimize",
        json={
            "stepId": 42,
            "paramKeys": ["exon_count"],
            "criterion": "find params that give 50-200 results",
            "budget": 5,
        },
    )
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    task_id = UUID(body["taskId"])
    message_id = UUID(body["messageId"])

    async with session_maker() as session:
        launch_events = (
            await session.scalars(
                select(ConversationEvent).where(
                    ConversationEvent.conversation_id
                    == conversation_with_step.id,
                ),
            )
        ).all()
        launch_envelope = next(
            e.chunk for e in launch_events
            if e.chunk.get("type") == "user-message"
            and e.chunk.get("message", {}).get("id") == str(message_id)
        )
        envelope_part = launch_envelope["message"]["parts"][0]
        assert envelope_part["type"] == "data-optimize-launch"
        data = envelope_part["data"]
        assert data["stepId"] == 42
        assert data["paramKeys"] == ["exon_count"]
        assert data["criterion"] == "find params that give 50-200 results"
        assert data["budget"] == 5

        bg = await session.get(BackgroundTask, task_id)
        assert bg is not None
        assert bg.tool_name == "optimize_search_parameters"
        assert bg.status == "pending"
        assert bg.conversation_id == conversation_with_step.id
        kwargs = bg.args["kwargs"]
        assert kwargs["target"]["search_name"] == "GenesByExonCount"
        assert kwargs["target"]["parameter_space"][0]["name"] == "exon_count"
        assert kwargs["settings"]["budget"] == 5

        events = (
            await session.scalars(
                select(ConversationEvent).where(
                    ConversationEvent.conversation_id
                    == conversation_with_step.id,
                    ConversationEvent.task_id.is_(None),
                ),
            )
        ).all()
        started = [
            e for e in events
            if e.chunk.get("type") == "data-background-task-started"
        ]
        assert len(started) == 1
        assert started[0].chunk["data"]["taskId"] == str(task_id)


async def test_launch_optimize_unknown_param_key_returns_409(
    api_client: httpx.AsyncClient,
    conversation_with_step: Conversation,
    patch_discovery: None,
    procrastinate_open: None,
) -> None:
    del patch_discovery, procrastinate_open
    response = await api_client.post(
        f"/api/v1/conversations/{conversation_with_step.id}/launchers/optimize",
        json={
            "stepId": 42,
            "paramKeys": ["not_a_real_param"],
            "criterion": "anything",
            "budget": 5,
        },
    )
    assert response.status_code == 409, response.text
    assert response.json()["code"] == "SPECIALIST_PRECONDITION_FAILED"


async def test_launch_optimize_unknown_step_returns_409(
    api_client: httpx.AsyncClient,
    conversation_with_step: Conversation,
    patch_discovery: None,
    procrastinate_open: None,
) -> None:
    del patch_discovery, procrastinate_open
    response = await api_client.post(
        f"/api/v1/conversations/{conversation_with_step.id}/launchers/optimize",
        json={
            "stepId": 999,
            "paramKeys": ["exon_count"],
            "criterion": "anything",
            "budget": 5,
        },
    )
    assert response.status_code == 409, response.text
    assert response.json()["code"] == "SPECIALIST_PRECONDITION_FAILED"


async def test_launch_optimize_no_steps_returns_409(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    seed_user: User,
    procrastinate_open: None,
) -> None:
    del procrastinate_open
    conv = Conversation(
        id=uuid4(),
        user_id=seed_user.id,
        site_id="plasmodb",
        name="empty",
        step_count=0,
        strategy_ast={},
    )
    db_session.add(conv)
    await db_session.flush()
    await db_session.commit()
    response = await api_client.post(
        f"/api/v1/conversations/{conv.id}/launchers/optimize",
        json={
            "stepId": 1,
            "paramKeys": ["x"],
            "criterion": "anything",
            "budget": 5,
        },
    )
    assert response.status_code == 409
    assert response.json()["code"] == "SPECIALIST_PRECONDITION_FAILED"


async def test_launch_optimize_session_conflict_specialist_active(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    conversation_with_step: Conversation,
    patch_discovery: None,
    procrastinate_open: None,
) -> None:
    del patch_discovery, procrastinate_open
    conversation_with_step.specialist_mode = {
        "kind": "validate",
        "enteredAt": "2026-04-26T00:00:00+00:00",
        "modelId": "claude-opus-4-7",
        "context": {},
    }
    db_session.add(conversation_with_step)
    await db_session.commit()
    response = await api_client.post(
        f"/api/v1/conversations/{conversation_with_step.id}/launchers/optimize",
        json={
            "stepId": 42,
            "paramKeys": ["exon_count"],
            "criterion": "anything",
            "budget": 5,
        },
    )
    assert response.status_code == 409
    assert response.json()["code"] == "SESSION_CONFLICT"


async def test_launch_optimize_session_conflict_active_durable(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    conversation_with_step: Conversation,
    patch_discovery: None,
    procrastinate_open: None,
) -> None:
    del patch_discovery, procrastinate_open
    db_session.add(
        BackgroundTask(
            id=uuid4(),
            conversation_id=conversation_with_step.id,
            user_id=conversation_with_step.user_id,
            tool_name="run_control_tests_on_step",
            status="running",
            args={},
            estimated_duration_seconds=300,
        ),
    )
    await db_session.commit()
    response = await api_client.post(
        f"/api/v1/conversations/{conversation_with_step.id}/launchers/optimize",
        json={
            "stepId": 42,
            "paramKeys": ["exon_count"],
            "criterion": "anything",
            "budget": 5,
        },
    )
    assert response.status_code == 409
    assert response.json()["code"] == "SESSION_CONFLICT"


async def test_launch_optimize_wrong_user_returns_404(
    app: FastAPI,
    db_session: AsyncSession,
    conversation_with_step: Conversation,
    patch_app_db_engine: None,
) -> None:
    del patch_app_db_engine
    other = User(id=uuid4())
    db_session.add(other)
    await db_session.flush()
    await db_session.commit()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"X-Requested-With": "XMLHttpRequest"},
    ) as client:
        client.cookies.set(
            "pathfinder-auth", create_user_token(other.id),
        )
        response = await client.post(
            f"/api/v1/conversations/{conversation_with_step.id}"
            "/launchers/optimize",
            json={
                "stepId": 42,
                "paramKeys": ["exon_count"],
                "criterion": "anything",
                "budget": 5,
            },
        )
    assert response.status_code in (403, 404)
