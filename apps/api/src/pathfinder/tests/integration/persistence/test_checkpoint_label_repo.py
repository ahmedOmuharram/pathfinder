from __future__ import annotations

from uuid import uuid4

import pytest

from pathfinder.persistence.models import User
from pathfinder.persistence.repositories.checkpoint_label import (
    CheckpointLabelRepository,
)
from pathfinder.persistence.session import async_session_factory


@pytest.fixture
async def repo(
    db_cleaner: None, patch_app_db_engine: None
) -> CheckpointLabelRepository:
    del db_cleaner, patch_app_db_engine
    return CheckpointLabelRepository(session_factory=async_session_factory)


@pytest.mark.asyncio
async def test_set_label_inserts_row_and_returns_it(
    repo: CheckpointLabelRepository,
) -> None:
    user_id = uuid4()
    async with async_session_factory() as session:
        session.add(User(id=user_id))
        await session.commit()

    row = await repo.set_label(
        thread_id="thread-1",
        checkpoint_id="cp-1",
        user_id=user_id,
        label="draft 1",
        pinned=False,
    )
    assert row.thread_id == "thread-1"
    assert row.checkpoint_id == "cp-1"
    assert row.user_id == user_id
    assert row.label == "draft 1"
    assert row.pinned is False


@pytest.mark.asyncio
async def test_set_label_idempotent_upsert(
    repo: CheckpointLabelRepository,
) -> None:
    user_id = uuid4()
    async with async_session_factory() as session:
        session.add(User(id=user_id))
        await session.commit()

    await repo.set_label(
        thread_id="t",
        checkpoint_id="c",
        user_id=user_id,
        label="draft 1",
        pinned=False,
    )
    await repo.set_label(
        thread_id="t",
        checkpoint_id="c",
        user_id=user_id,
        label="draft 2",
        pinned=True,
    )
    rows = await repo.list_for_thread(thread_id="t", user_id=user_id)
    assert len(rows) == 1
    assert rows[0].label == "draft 2"
    assert rows[0].pinned is True


@pytest.mark.asyncio
async def test_delete_label(
    repo: CheckpointLabelRepository,
) -> None:
    user_id = uuid4()
    async with async_session_factory() as session:
        session.add(User(id=user_id))
        await session.commit()

    await repo.set_label(
        thread_id="t",
        checkpoint_id="c",
        user_id=user_id,
        label="x",
        pinned=False,
    )
    await repo.delete_label(thread_id="t", checkpoint_id="c", user_id=user_id)
    rows = await repo.list_for_thread(thread_id="t", user_id=user_id)
    assert rows == []


@pytest.mark.asyncio
async def test_list_for_thread_filters_by_thread_and_user(
    repo: CheckpointLabelRepository,
) -> None:
    user_a = uuid4()
    user_b = uuid4()
    async with async_session_factory() as session:
        session.add(User(id=user_a))
        session.add(User(id=user_b))
        await session.commit()

    await repo.set_label(
        thread_id="t1", checkpoint_id="c1", user_id=user_a, label="A1", pinned=False
    )
    await repo.set_label(
        thread_id="t1", checkpoint_id="c2", user_id=user_a, label="A2", pinned=True
    )
    await repo.set_label(
        thread_id="t1", checkpoint_id="c1", user_id=user_b, label="B1", pinned=False
    )
    await repo.set_label(
        thread_id="t2", checkpoint_id="c1", user_id=user_a, label="other", pinned=False
    )

    rows_a = await repo.list_for_thread(thread_id="t1", user_id=user_a)
    assert {r.checkpoint_id for r in rows_a} == {"c1", "c2"}
    assert {r.label for r in rows_a} == {"A1", "A2"}

    rows_b = await repo.list_for_thread(thread_id="t1", user_id=user_b)
    assert len(rows_b) == 1
    assert rows_b[0].label == "B1"


@pytest.mark.asyncio
async def test_set_label_with_none_clears_label_keeps_pin(
    repo: CheckpointLabelRepository,
) -> None:
    user_id = uuid4()
    async with async_session_factory() as session:
        session.add(User(id=user_id))
        await session.commit()

    await repo.set_label(
        thread_id="t",
        checkpoint_id="c",
        user_id=user_id,
        label="initial",
        pinned=True,
    )
    await repo.set_label(
        thread_id="t",
        checkpoint_id="c",
        user_id=user_id,
        label=None,
        pinned=True,
    )
    rows = await repo.list_for_thread(thread_id="t", user_id=user_id)
    assert len(rows) == 1
    assert rows[0].label is None
    assert rows[0].pinned is True


@pytest.mark.asyncio
async def test_delete_missing_label_is_noop(
    repo: CheckpointLabelRepository,
) -> None:
    user_id = uuid4()
    async with async_session_factory() as session:
        session.add(User(id=user_id))
        await session.commit()

    await repo.delete_label(thread_id="t", checkpoint_id="missing", user_id=user_id)
    rows = await repo.list_for_thread(thread_id="t", user_id=user_id)
    assert rows == []
