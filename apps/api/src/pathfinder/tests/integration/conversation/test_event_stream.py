from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

import pytest

import pathfinder.platform.db as session_module
from pathfinder.assistant_core.conversation.event_stream import replay_and_tail
from pathfinder.assistant_core.conversation.event_writer import ChatEventWriter
from pathfinder.persistence.models import Conversation, User


async def _seed_conversation() -> tuple[UUID, UUID]:
    user_id = uuid4()
    conv_id = uuid4()
    turn_id = uuid4()
    async with session_module.async_session_factory() as session:
        session.add(User(id=user_id))
        session.add(
            Conversation(
                id=conv_id,
                user_id=user_id,
                site_id="plasmodb",
                name="t",
            ),
        )
        await session.commit()
    return conv_id, turn_id


@pytest.mark.asyncio
async def test_replay_returns_events_past_cursor(
    patch_app_db_engine: None,
    db_cleaner: None,
) -> None:
    del patch_app_db_engine, db_cleaner
    conv_id, turn_id = await _seed_conversation()
    writer = ChatEventWriter(conversation_id=conv_id, turn_id=turn_id)
    id1 = await writer.write({"type": "text-start", "id": "a"})
    id2 = await writer.write({"type": "text-delta", "id": "a", "delta": "x"})
    id3 = await writer.write({"type": "text-end", "id": "a"})

    collected: list[tuple[int, dict]] = []

    async def consume() -> None:
        async for event_id, chunk in replay_and_tail(
            conversation_id=conv_id,
            after=id1,
        ):
            collected.append((event_id, chunk))
            if event_id >= id3:
                break

    await asyncio.wait_for(consume(), timeout=5)
    assert [e[0] for e in collected] == [id2, id3]
    assert collected[0][1]["type"] == "text-delta"


@pytest.mark.asyncio
async def test_tail_yields_events_produced_after_subscribe(
    patch_app_db_engine: None,
    db_cleaner: None,
) -> None:
    del patch_app_db_engine, db_cleaner
    conv_id, turn_id = await _seed_conversation()
    writer = ChatEventWriter(conversation_id=conv_id, turn_id=turn_id)
    collected: list[tuple[int, dict]] = []

    async def consume() -> None:
        async for event_id, chunk in replay_and_tail(
            conversation_id=conv_id,
            after=0,
        ):
            collected.append((event_id, chunk))
            if len(collected) >= 3:
                break

    async def produce() -> None:
        await asyncio.sleep(0.3)
        await writer.write({"type": "text-start", "id": "a"})
        await writer.write({"type": "text-delta", "id": "a", "delta": "x"})
        await writer.write({"type": "text-end", "id": "a"})

    await asyncio.wait_for(
        asyncio.gather(consume(), produce()),
        timeout=10,
    )
    assert [c["type"] for _, c in collected] == [
        "text-start",
        "text-delta",
        "text-end",
    ]
