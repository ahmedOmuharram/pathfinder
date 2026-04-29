from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pathfinder.ai.conversation.event_stream import iter_sse
from pathfinder.ai.conversation.event_writer import ChatEventWriter
from pathfinder.ai.conversation.ui_message_reducer import (
    reduce_chunks_to_messages,
    user_message_chunk,
)
from pathfinder.persistence.models import Conversation, User
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
async def conversation(
    db_session: AsyncSession, seed_user: User,
) -> Conversation:
    conv = Conversation(
        id=uuid4(),
        user_id=seed_user.id,
        site_id="plasmodb",
        record_type="transcript",
        name="snapshot-fixture",
        step_count=0,
        strategy_ast={},
    )
    db_session.add(conv)
    await db_session.flush()
    await db_session.commit()
    return conv


@pytest.fixture
async def api_client(
    app: FastAPI, seed_user: User,
) -> AsyncGenerator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    token = create_user_token(seed_user.id)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"authorization": f"Bearer {token}"},
    ) as client:
        yield client


async def _seed_chunks(
    *, conversation_id: UUID, chunks: list[dict[str, Any]],
) -> None:
    writer = ChatEventWriter(
        conversation_id=conversation_id, turn_id=uuid4(),
    )
    for chunk in chunks:
        await writer.write(chunk)


async def test_snapshot_returns_empty_log_for_new_conversation(
    api_client: httpx.AsyncClient, conversation: Conversation,
) -> None:
    response = await api_client.get(
        f"/api/v1/conversations/{conversation.id}/events/snapshot",
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["chunks"] == []
    assert body["cursor"] == 0


async def test_snapshot_returns_full_chunk_log(
    api_client: httpx.AsyncClient, conversation: Conversation,
) -> None:
    user_id = uuid4()
    assistant_id = uuid4()
    seeded = [
        user_message_chunk(
            message_id=str(user_id),
            parts=[{"type": "text", "text": "what's the count?"}],
        ),
        {"type": "start", "messageId": str(assistant_id)},
        {"type": "text-start", "id": "t1"},
        {"type": "text-delta", "id": "t1", "delta": "the count is 42"},
        {"type": "text-end", "id": "t1"},
        {"type": "finish", "finishReason": "stop"},
        {"type": "done"},
    ]
    await _seed_chunks(
        conversation_id=conversation.id, chunks=seeded,
    )
    response = await api_client.get(
        f"/api/v1/conversations/{conversation.id}/events/snapshot",
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["cursor"] > 0
    assert len(body["chunks"]) == len(seeded)
    types = [c["type"] for c in body["chunks"]]
    assert types[0] == "user-message"
    assert types[-1] == "done"


async def test_snapshot_round_trips_through_reducer(
    api_client: httpx.AsyncClient, conversation: Conversation,
) -> None:
    user_id = uuid4()
    assistant_id = uuid4()
    seeded = [
        user_message_chunk(
            message_id=str(user_id),
            parts=[{"type": "text", "text": "ping"}],
        ),
        {"type": "start", "messageId": str(assistant_id)},
        {"type": "text-start", "id": "t1"},
        {"type": "text-delta", "id": "t1", "delta": "pong"},
        {"type": "text-end", "id": "t1"},
        {"type": "done"},
    ]
    await _seed_chunks(
        conversation_id=conversation.id, chunks=seeded,
    )
    response = await api_client.get(
        f"/api/v1/conversations/{conversation.id}/events/snapshot",
    )
    body = response.json()
    messages = reduce_chunks_to_messages(body["chunks"])
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[0]["id"] == str(user_id)
    assert messages[0]["parts"][0]["text"] == "ping"
    assert messages[1]["id"] == str(assistant_id)
    text_parts = [
        p for p in messages[1]["parts"] if p["type"] == "text"
    ]
    assert text_parts[0]["text"] == "pong"


async def test_snapshot_caps_at_in_flight_user_message(
    api_client: httpx.AsyncClient, conversation: Conversation,
) -> None:
    user_a = uuid4()
    asst_a = uuid4()
    user_b = uuid4()
    asst_b = uuid4()
    seeded = [
        user_message_chunk(
            message_id=str(user_a),
            parts=[{"type": "text", "text": "first"}],
        ),
        {"type": "start", "messageId": str(asst_a)},
        {"type": "text-start", "id": "t1"},
        {"type": "text-delta", "id": "t1", "delta": "first reply"},
        {"type": "text-end", "id": "t1"},
        {"type": "done"},
        user_message_chunk(
            message_id=str(user_b),
            parts=[{"type": "text", "text": "second"}],
        ),
        {"type": "start", "messageId": str(asst_b)},
        {"type": "text-start", "id": "t2"},
        {"type": "text-delta", "id": "t2", "delta": "partial"},
    ]
    await _seed_chunks(
        conversation_id=conversation.id, chunks=seeded,
    )
    response = await api_client.get(
        f"/api/v1/conversations/{conversation.id}/events/snapshot",
    )
    body = response.json()
    types = [c["type"] for c in body["chunks"]]
    assert types == [
        "user-message",
        "start",
        "text-start",
        "text-delta",
        "text-end",
        "done",
        "user-message",
    ]
    messages = reduce_chunks_to_messages(body["chunks"])
    assert [m["role"] for m in messages] == ["user", "assistant", "user"]
    assert messages[2]["id"] == str(user_b)


async def test_snapshot_ignores_rogue_mid_turn_user_message(
    api_client: httpx.AsyncClient, conversation: Conversation,
) -> None:
    user_a = uuid4()
    asst_a = uuid4()
    user_rogue = uuid4()
    seeded = [
        user_message_chunk(
            message_id=str(user_a),
            parts=[{"type": "text", "text": "kick off"}],
        ),
        {"type": "start", "messageId": str(asst_a)},
        {
            "type": "tool-input-start",
            "toolCallId": "call_X",
            "toolName": "do_thing",
        },
        {
            "type": "tool-input-delta",
            "toolCallId": "call_X",
            "inputTextDelta": "{",
        },
        user_message_chunk(
            message_id=str(user_rogue),
            parts=[{"type": "text", "text": "rogue mid-turn"}],
        ),
        {
            "type": "tool-input-delta",
            "toolCallId": "call_X",
            "inputTextDelta": "}",
        },
    ]
    await _seed_chunks(
        conversation_id=conversation.id, chunks=seeded,
    )
    response = await api_client.get(
        f"/api/v1/conversations/{conversation.id}/events/snapshot",
    )
    body = response.json()
    types = [c["type"] for c in body["chunks"]]
    assert types == ["user-message"]
    assert body["chunks"][0]["message"]["id"] == str(user_a)


def _parse_sse_frames(frames: list[str]) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for frame in frames:
        for line in frame.splitlines():
            if not line.startswith("data: "):
                continue
            payload = line[len("data: "):]
            if payload == "[DONE]":
                chunks.append({"type": "done"})
                continue
            chunks.append(json.loads(payload))
    return chunks


def _assert_tool_chunks_well_formed(chunks: list[dict[str, Any]]) -> None:
    seen_starts: set[str] = set()
    for chunk in chunks:
        ctype = chunk.get("type")
        tcid = chunk.get("toolCallId")
        if ctype == "tool-input-start" and isinstance(tcid, str):
            seen_starts.add(tcid)
            continue
        if ctype in {
            "tool-input-delta",
            "tool-input-available",
            "tool-input-error",
            "tool-output-available",
            "tool-output-error",
        } and isinstance(tcid, str):
            assert tcid in seen_starts, (
                f"{ctype} for {tcid} arrived without a preceding "
                f"tool-input-start in the resume stream"
            )


async def test_resume_stream_after_snapshot_cap_replays_tool_input_start(
    api_client: httpx.AsyncClient, conversation: Conversation,
) -> None:
    """Reproduces the prod failure: an in-flight assistant turn with an
    open tool call, plus a rogue user-message persisted mid-turn. The
    snapshot endpoint must cap such that the SSE replay served by
    `/events?after=cursor` still begins before the tool-input-start —
    otherwise the SDK errors with `tool-input-delta for missing tool call`.
    """
    user_a = uuid4()
    asst_a = uuid4()
    user_first = uuid4()
    asst_b = uuid4()
    user_rogue = uuid4()
    in_flight = [
        user_message_chunk(
            message_id=str(user_a),
            parts=[{"type": "text", "text": "warm-up"}],
        ),
        {"type": "start", "messageId": str(asst_a)},
        {"type": "text-start", "id": "t0"},
        {"type": "text-delta", "id": "t0", "delta": "ok"},
        {"type": "text-end", "id": "t0"},
        {"type": "finish"},
        {"type": "done"},
        user_message_chunk(
            message_id=str(user_first),
            parts=[{"type": "text", "text": "now do the thing"}],
        ),
        {"type": "start", "messageId": str(asst_b)},
        {
            "type": "tool-input-start",
            "toolCallId": "call_inflight",
            "toolName": "do_thing",
        },
        {
            "type": "tool-input-delta",
            "toolCallId": "call_inflight",
            "inputTextDelta": "{\"q\":",
        },
        user_message_chunk(
            message_id=str(user_rogue),
            parts=[{"type": "text", "text": "rogue mid-turn"}],
        ),
        {
            "type": "tool-input-delta",
            "toolCallId": "call_inflight",
            "inputTextDelta": "\"x\"}",
        },
    ]
    await _seed_chunks(conversation_id=conversation.id, chunks=in_flight)

    snap = (
        await api_client.get(
            f"/api/v1/conversations/{conversation.id}/events/snapshot",
        )
    ).json()
    snap_messages = reduce_chunks_to_messages(snap["chunks"])
    assert [m["role"] for m in snap_messages] == ["user", "assistant", "user"]
    assert snap_messages[2]["id"] == str(user_first)

    completion = [
        {
            "type": "tool-input-available",
            "toolCallId": "call_inflight",
            "toolName": "do_thing",
            "input": {"q": "x"},
        },
        {"type": "finish"},
        {"type": "done"},
    ]
    await _seed_chunks(conversation_id=conversation.id, chunks=completion)

    frames: list[str] = []
    async for frame in iter_sse(
        conversation_id=conversation.id, after=snap["cursor"],
    ):
        frames.append(frame)
    resume_chunks = _parse_sse_frames(frames)

    resume_types = [c["type"] for c in resume_chunks]
    assert resume_types[0] == "start"
    assert "tool-input-start" in resume_types
    assert resume_types[-1] == "done"
    assert "user-message" not in resume_types

    _assert_tool_chunks_well_formed(resume_chunks)


async def test_snapshot_404_for_other_users_conversation(
    app: FastAPI,
    db_session: AsyncSession,
    conversation: Conversation,
) -> None:
    other = User(id=uuid4())
    db_session.add(other)
    await db_session.flush()
    await db_session.commit()
    transport = httpx.ASGITransport(app=app)
    token = create_user_token(other.id)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"authorization": f"Bearer {token}"},
    ) as client:
        response = await client.get(
            f"/api/v1/conversations/{conversation.id}/events/snapshot",
        )
    assert response.status_code == 404
