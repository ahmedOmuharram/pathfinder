from collections.abc import AsyncIterator

import httpx
import pytest
from sqlalchemy import text

from pathfinder.platform import db as session_module
from pathfinder.platform.health import worker_is_alive
from pathfinder.platform.readiness import (
    _FIXED_SUBSYSTEMS,
    get_readiness,
    reset_readiness,
)


async def _clear_workers() -> None:
    async with session_module.async_session_factory() as session:
        await session.execute(text("DELETE FROM procrastinate_workers"))
        await session.commit()


async def _insert_worker_heartbeat(*, age_seconds: float) -> None:
    async with session_module.async_session_factory() as session:
        await session.execute(
            text(
                "INSERT INTO procrastinate_workers (last_heartbeat) "
                "VALUES (now() - make_interval(secs => :s))"
            ),
            {"s": age_seconds},
        )
        await session.commit()


@pytest.fixture
async def api_ready() -> AsyncIterator[None]:
    state = get_readiness()
    for name in _FIXED_SUBSYSTEMS:
        state.mark_ready(name)
    yield
    reset_readiness()


async def test_worker_is_alive_true_for_fresh_heartbeat(
    patch_app_db_engine: None,
    db_cleaner: None,
) -> None:
    del patch_app_db_engine, db_cleaner
    await _clear_workers()
    await _insert_worker_heartbeat(age_seconds=5)
    async with session_module.async_session_factory() as session:
        assert await worker_is_alive(session) is True
    await _clear_workers()


async def test_worker_is_alive_false_for_stale_heartbeat(
    patch_app_db_engine: None,
    db_cleaner: None,
) -> None:
    del patch_app_db_engine, db_cleaner
    await _clear_workers()
    await _insert_worker_heartbeat(age_seconds=120)
    async with session_module.async_session_factory() as session:
        assert await worker_is_alive(session) is False
    await _clear_workers()


async def test_worker_is_alive_false_when_no_workers(
    patch_app_db_engine: None,
    db_cleaner: None,
) -> None:
    del patch_app_db_engine, db_cleaner
    await _clear_workers()
    async with session_module.async_session_factory() as session:
        assert await worker_is_alive(session) is False


async def test_system_ready_true_when_api_ready_and_worker_alive(
    client: httpx.AsyncClient,
    api_ready: None,
) -> None:
    del api_ready
    await _clear_workers()
    await _insert_worker_heartbeat(age_seconds=2)
    resp = await client.get("/health/system")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ready"] is True
    assert body["apiReady"] is True
    assert body["workerAlive"] is True
    assert body["notReady"] == []
    await _clear_workers()


async def test_system_ready_false_when_worker_dead(
    client: httpx.AsyncClient,
    api_ready: None,
) -> None:
    del api_ready
    await _clear_workers()
    resp = await client.get("/health/system")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ready"] is False
    assert body["apiReady"] is True
    assert body["workerAlive"] is False
    assert "worker" in body["notReady"]


async def test_system_ready_false_when_api_not_ready(
    client: httpx.AsyncClient,
) -> None:
    reset_readiness()
    await _clear_workers()
    await _insert_worker_heartbeat(age_seconds=2)
    resp = await client.get("/health/system")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ready"] is False
    assert body["apiReady"] is False
    assert body["workerAlive"] is True
    await _clear_workers()
