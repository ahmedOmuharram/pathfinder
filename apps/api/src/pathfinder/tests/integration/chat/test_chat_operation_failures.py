"""Regression coverage for chat startup failures and stream termination."""

import asyncio
import json
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select

import pathfinder.persistence.session as session_module
from pathfinder.persistence.models import Operation, User
from pathfinder.platform.event_schemas import PipelineConfig, PipelinePhaseConfig
from pathfinder.platform.security import create_user_token
from pathfinder.platform.types import JSONObject

_MOCK_PHASE = PipelinePhaseConfig(model_id="mock/deterministic", reasoning_effort="low")
_MOCK_PIPELINE = PipelineConfig(
    scoping=_MOCK_PHASE,
    discovery=_MOCK_PHASE,
    planning=_MOCK_PHASE,
    execution=_MOCK_PHASE,
    verification=_MOCK_PHASE,
)


async def _collect_operation_events(
    client: httpx.AsyncClient,
    *,
    operation_id: str,
) -> list[JSONObject]:
    events: list[JSONObject] = []
    buffer = ""

    async with client.stream(
        "GET",
        f"/api/v1/operations/{operation_id}/subscribe",
        timeout=30.0,
    ) as response:
        assert response.status_code == 200
        async for chunk in response.aiter_text():
            buffer += chunk
            while "\n\n" in buffer:
                raw, buffer = buffer.split("\n\n", 1)
                part = raw.strip()
                if not part:
                    continue
                event_type: str | None = None
                data_raw: str | None = None
                for line in part.splitlines():
                    if line.startswith("event:"):
                        event_type = line.removeprefix("event:").strip()
                    elif line.startswith("data:"):
                        data_raw = line.removeprefix("data:").strip()
                if not event_type or data_raw is None:
                    continue
                data = json.loads(data_raw)
                if not isinstance(data, dict):
                    continue
                events.append({"type": event_type, "data": data})
                if event_type == "message_end":
                    return events

    return events


async def _wait_for_operation_completion(operation_id: str) -> None:
    for _ in range(50):
        async with session_module.async_session_factory() as session:
            result = await session.execute(
                select(Operation).where(Operation.operation_id == operation_id)
            )
            operation = result.scalar_one()
            if operation.status == "completed":
                return
        await asyncio.sleep(0.1)

    msg = f"Operation {operation_id} did not complete in time"
    raise AssertionError(msg)


@pytest.mark.asyncio
async def test_chat_startup_failure_emits_error_and_message_end(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = uuid4()
    async with session_module.async_session_factory() as session:
        session.add(User(id=user_id))
        await session.commit()

    client.cookies.set("pathfinder-auth", create_user_token(user_id))

    message = "boom before message_start"

    async def _boom(*args: object, **kwargs: object) -> object:
        raise RuntimeError(message)

    monkeypatch.setattr(
        "pathfinder.services.chat.producer.build_agent_deps",
        _boom,
    )

    response = await client.post(
        "/api/v1/chat",
        json={
            "siteId": "plasmodb",
            "message": "Which P. vivax genes are likely membrane transporters?",
            "pipeline": _MOCK_PIPELINE.model_dump(by_alias=True),
        },
        timeout=30.0,
    )

    assert response.status_code == 202
    body = response.json()
    operation_id = body["operationId"]

    events = await _collect_operation_events(client, operation_id=operation_id)
    assert [event["type"] for event in events][-1] == "message_end"
    assert any(event["type"] == "error" for event in events)

    async with session_module.async_session_factory() as session:
        result = await session.execute(
            select(Operation).where(Operation.operation_id == operation_id)
        )
        operation = result.scalar_one()
        assert operation.status == "failed"
        assert operation.completed_at is not None


@pytest.mark.asyncio
async def test_completed_chat_operation_replays_full_stream_to_late_subscriber(
    client: httpx.AsyncClient,
) -> None:
    user_id = uuid4()
    async with session_module.async_session_factory() as session:
        session.add(User(id=user_id))
        await session.commit()

    client.cookies.set("pathfinder-auth", create_user_token(user_id))

    response = await client.post(
        "/api/v1/chat",
        json={
            "siteId": "plasmodb",
            "message": "Which P. vivax genes are likely membrane transporters?",
            "pipeline": _MOCK_PIPELINE.model_dump(by_alias=True),
        },
        timeout=30.0,
    )

    assert response.status_code == 202
    operation_id = response.json()["operationId"]

    await _wait_for_operation_completion(operation_id)

    events = await _collect_operation_events(client, operation_id=operation_id)
    event_types = [event["type"] for event in events]

    assert event_types[-1] == "message_end"
    assert "assistant_message" in event_types
    assert "message_start" in event_types
