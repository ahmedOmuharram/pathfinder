"""End-to-end tests for the POST /chat → enqueue → worker → SSE + GET /events cycle.

Covers:
- POST /chat enqueues a job, the in-process worker drains it, and the POST
  streaming response contains [DONE] + ≥ 3 ``data:`` frames.
- POST /chat on a conversation that already has a completed prior turn uses
  a fresh baseline cursor — the new response does NOT replay prior events.
- GET /conversations/{id}/events returns 204 when the latest event is ``done``
  (or when there are no events). Matches the AI SDK v6 ``reconnectToStream``
  contract: nothing to resume.
- GET /conversations/{id}/events streams when the latest event is not
  ``done`` (turn in-flight, reconnect should tail live).
- Two concurrent GETs are consistent: both 204 when caught up.

LLM provider: the conftest sets ``PATHFINDER_CHAT_PROVIDER=mock`` before any
pathfinder import, so no real LLM calls are made.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI
from procrastinate.testing import InMemoryConnector

import pathfinder.platform.db as session_module
from pathfinder.ai.conversation.event_writer import ChatEventWriter
from pathfinder.jobs.app import procrastinate_app
from pathfinder.jobs.tasks import ensure_registered
from pathfinder.persistence.models import Conversation
from pathfinder.platform.security import create_user_token


def _event_ids(body: str) -> list[int]:
    return [
        int(line.split(":", 1)[1].strip())
        for line in body.splitlines()
        if line.startswith("id:")
    ]


@pytest.fixture
async def in_memory_jobs() -> AsyncIterator[InMemoryConnector]:
    """Swap procrastinate connector to InMemoryConnector for the duration of the test.

    Mirrors the existing ``patch_app_db_engine`` pattern — rebinds both
    ``procrastinate_app.connector`` and ``procrastinate_app.job_manager.connector``.
    Restores on teardown so other tests in the session aren't affected.
    """
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


async def _drain() -> None:
    """Run all queued chat_turn jobs in-process and return."""
    async with procrastinate_app.open_async():
        await procrastinate_app.run_worker_async(
            queues=["chat_turn"],
            wait=False,
            listen_notify=False,
            install_signal_handlers=False,
        )


async def _wait_until_enqueued(connector: InMemoryConnector) -> None:
    """Poll the InMemoryConnector until POST has enqueued a chat_turn job.

    Replaces a bare ``sleep(0.3)`` that went flaky on cold-start runs where
    the POST handler hadn't finished ``defer_async`` before drain kicked in
    (drain would see zero jobs and return immediately, hanging the POST tail).
    Wrap the caller with ``asyncio.timeout(...)`` to bound the wait.
    """
    while True:
        if any(j["task_name"] == "chat_turn:run" for j in connector.jobs.values()):
            return
        await asyncio.sleep(0.02)


def _post_body(conv_id: UUID) -> dict:
    msg_id = str(uuid4())
    return {
        "trigger": "submit-message",
        "id": msg_id,
        "messages": [
            {
                "id": msg_id,
                "role": "user",
                "parts": [{"type": "text", "text": "hi"}],
            },
        ],
        "conversationId": str(conv_id),
        "siteId": "plasmodb",
    }


async def _seed_conversation(user_id: UUID) -> UUID:
    """Insert a conversation row for a pre-existing user id. Used when we
    want to attach events without going through the POST /chat path."""
    conv_id = uuid4()
    async with session_module.async_session_factory() as session:
        session.add(
            Conversation(
                id=conv_id,
                user_id=user_id,
                site_id="plasmodb",
                name="t",
            ),
        )
        await session.commit()
    return conv_id


async def test_post_chat_enqueues_runs_and_streams_until_done(
    app: FastAPI,
    patch_app_db_engine: None,
    db_cleaner: None,
    authed_user_id: UUID,
    in_memory_jobs: InMemoryConnector,
) -> None:
    del patch_app_db_engine, db_cleaner
    conv_id = uuid4()
    token = create_user_token(authed_user_id)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        cookies={"pathfinder-auth": token},
        headers={"X-Requested-With": "XMLHttpRequest"},
    ) as client:
        post_task = asyncio.create_task(
            client.post(
                "/api/v1/chat",
                json=_post_body(conv_id),
                timeout=30.0,
            ),
        )
        await asyncio.wait_for(_wait_until_enqueued(in_memory_jobs), timeout=5.0)
        await _drain()
        post_res = await asyncio.wait_for(post_task, timeout=30.0)

    assert post_res.status_code == 200
    body = post_res.text
    assert "[DONE]" in body
    assert body.count("data:") >= 3


async def test_post_chat_does_not_replay_prior_turn_events(
    app: FastAPI,
    patch_app_db_engine: None,
    db_cleaner: None,
    authed_user_id: UUID,
    in_memory_jobs: InMemoryConnector,
) -> None:
    """Seed a completed prior turn, POST a new turn, verify the POST
    response only contains new-turn event ids (no replay + no early termination
    on the prior turn's DoneChunk)."""
    del patch_app_db_engine, db_cleaner
    conv_id = await _seed_conversation(authed_user_id)
    # Simulate a prior completed turn: 3 non-done chunks + 1 done chunk.
    prior_writer = ChatEventWriter(
        conversation_id=conv_id,
        turn_id=uuid4(),
    )
    await prior_writer.write({"type": "start", "messageId": "prior"})
    await prior_writer.write({"type": "text-start", "id": "a"})
    await prior_writer.write({"type": "text-delta", "id": "a", "delta": "old"})
    prior_done_id = await prior_writer.write({"type": "done"})

    token = create_user_token(authed_user_id)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        cookies={"pathfinder-auth": token},
        headers={"X-Requested-With": "XMLHttpRequest"},
    ) as client:
        post_task = asyncio.create_task(
            client.post(
                "/api/v1/chat",
                json=_post_body(conv_id),
                timeout=30.0,
            ),
        )
        await asyncio.wait_for(_wait_until_enqueued(in_memory_jobs), timeout=5.0)
        await _drain()
        post_res = await asyncio.wait_for(post_task, timeout=30.0)

    assert post_res.status_code == 200
    ids = _event_ids(post_res.text)
    # Every streamed id must be past the prior ``done``.
    assert len(ids) >= 1
    assert all(i > prior_done_id for i in ids), (
        f"POST replayed prior events (ids ≤ {prior_done_id}): {ids}"
    )


async def test_events_endpoint_returns_204_when_turn_complete(
    app: FastAPI,
    patch_app_db_engine: None,
    db_cleaner: None,
    authed_user_id: UUID,
    in_memory_jobs: InMemoryConnector,
) -> None:
    """After the POST completes (latest event = ``done``), GET /events returns
    204 per the AI SDK v6 ``reconnectToStream`` contract — nothing to replay."""
    del patch_app_db_engine, db_cleaner
    conv_id = uuid4()
    token = create_user_token(authed_user_id)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        cookies={"pathfinder-auth": token},
        headers={"X-Requested-With": "XMLHttpRequest"},
    ) as client:
        post_task = asyncio.create_task(
            client.post(
                "/api/v1/chat",
                json=_post_body(conv_id),
                timeout=30.0,
            ),
        )
        await asyncio.wait_for(_wait_until_enqueued(in_memory_jobs), timeout=5.0)
        await _drain()
        post_res = await asyncio.wait_for(post_task, timeout=30.0)
        assert post_res.status_code == 200

        get_res = await client.get(
            f"/api/v1/conversations/{conv_id}/events",
            params={"after": "0"},
            timeout=5.0,
        )

    assert get_res.status_code == 204


async def test_events_endpoint_returns_204_on_empty_conversation(
    app: FastAPI,
    patch_app_db_engine: None,
    db_cleaner: None,
    authed_user_id: UUID,
) -> None:
    """A conversation with zero events has nothing to resume."""
    del patch_app_db_engine, db_cleaner
    conv_id = await _seed_conversation(authed_user_id)
    token = create_user_token(authed_user_id)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        cookies={"pathfinder-auth": token},
        headers={"X-Requested-With": "XMLHttpRequest"},
    ) as client:
        res = await client.get(
            f"/api/v1/conversations/{conv_id}/events",
            params={"after": "0"},
            timeout=5.0,
        )

    assert res.status_code == 204


async def test_events_endpoint_streams_when_last_event_is_not_done(
    app: FastAPI,
    patch_app_db_engine: None,
    db_cleaner: None,
    authed_user_id: UUID,
) -> None:
    """If the latest event is a non-done chunk (turn in-flight), the endpoint
    streams. We terminate the stream by writing a ``done`` chunk mid-tail."""
    del patch_app_db_engine, db_cleaner
    conv_id = await _seed_conversation(authed_user_id)
    writer = ChatEventWriter(conversation_id=conv_id, turn_id=uuid4())
    await writer.write({"type": "start", "messageId": "live"})
    await writer.write({"type": "text-start", "id": "a"})
    await writer.write({"type": "text-delta", "id": "a", "delta": "x"})
    token = create_user_token(authed_user_id)

    async def _finisher() -> None:
        await asyncio.sleep(0.3)
        await writer.write({"type": "text-end", "id": "a"})
        await writer.write({"type": "done"})

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        cookies={"pathfinder-auth": token},
        headers={"X-Requested-With": "XMLHttpRequest"},
    ) as client:
        finisher_task = asyncio.create_task(_finisher())
        res = await client.get(
            f"/api/v1/conversations/{conv_id}/events",
            params={"after": "0"},
            timeout=10.0,
        )
        await finisher_task

    assert res.status_code == 200
    assert "[DONE]" in res.text
    assert (
        res.text.count("data:") >= 4
    )  # start + text-start + text-delta + text-end + [DONE]


async def test_two_concurrent_subscribers_consistent_204_when_complete(
    app: FastAPI,
    patch_app_db_engine: None,
    db_cleaner: None,
    authed_user_id: UUID,
    in_memory_jobs: InMemoryConnector,
) -> None:
    """Two subscribers connecting after the turn completes both get 204."""
    del patch_app_db_engine, db_cleaner
    conv_id = uuid4()
    token = create_user_token(authed_user_id)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        cookies={"pathfinder-auth": token},
        headers={"X-Requested-With": "XMLHttpRequest"},
    ) as client:
        post_task = asyncio.create_task(
            client.post(
                "/api/v1/chat",
                json=_post_body(conv_id),
                timeout=30.0,
            ),
        )
        await asyncio.wait_for(_wait_until_enqueued(in_memory_jobs), timeout=5.0)
        await _drain()
        post_res = await asyncio.wait_for(post_task, timeout=30.0)
        assert post_res.status_code == 200

        res_a, res_b = await asyncio.gather(
            client.get(
                f"/api/v1/conversations/{conv_id}/events",
                params={"after": "0"},
                timeout=5.0,
            ),
            client.get(
                f"/api/v1/conversations/{conv_id}/events",
                params={"after": "0"},
                timeout=5.0,
            ),
        )

    assert res_a.status_code == 204
    assert res_b.status_code == 204
