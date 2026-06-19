from __future__ import annotations

from collections.abc import AsyncGenerator
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

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


async def _add_conv(
    session: AsyncSession,
    user_id: UUID,
    *,
    site_id: str,
    wdk_strategy_id: int | None,
) -> UUID:
    conv = Conversation(
        id=uuid4(),
        user_id=user_id,
        site_id=site_id,
        name="c",
        wdk_strategy_id=wdk_strategy_id,
    )
    session.add(conv)
    await session.flush()
    await session.commit()
    return conv.id


async def test_purge_dismisses_all_conversations_and_reports_counts(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    seed_user: User,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    no_wdk = await _add_conv(
        db_session, seed_user.id, site_id="plasmodb", wdk_strategy_id=None
    )
    wdk_linked = await _add_conv(
        db_session, seed_user.id, site_id="plasmodb", wdk_strategy_id=555
    )

    resp = await api_client.request(
        "DELETE", "/api/v1/user/data", params={"siteId": "plasmodb"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {
        "ok": True,
        "deleted": {
            "strategies": 2,
            "wdkStrategies": 0,
            "geneSets": 0,
            "experiments": 0,
            "controlSets": 0,
        },
    }

    async with session_maker() as verify:
        rows = (
            (
                await verify.execute(
                    select(Conversation).where(Conversation.user_id == seed_user.id)
                )
            )
            .scalars()
            .all()
        )
    by_id = {c.id: c for c in rows}
    assert set(by_id) == {no_wdk, wdk_linked}
    assert by_id[no_wdk].dismissed_at is not None
    assert by_id[wdk_linked].dismissed_at is not None


async def test_purge_respects_site_scope(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    seed_user: User,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    here = await _add_conv(
        db_session, seed_user.id, site_id="plasmodb", wdk_strategy_id=None
    )
    elsewhere = await _add_conv(
        db_session, seed_user.id, site_id="toxodb", wdk_strategy_id=None
    )

    resp = await api_client.request(
        "DELETE", "/api/v1/user/data", params={"siteId": "plasmodb"}
    )
    assert resp.status_code == 200
    assert resp.json()["deleted"]["strategies"] == 1

    async with session_maker() as verify:
        rows = {
            c.id: c
            for c in (
                await verify.execute(
                    select(Conversation).where(Conversation.user_id == seed_user.id)
                )
            )
            .scalars()
            .all()
        }
    assert rows[here].dismissed_at is not None
    assert rows[elsewhere].dismissed_at is None
