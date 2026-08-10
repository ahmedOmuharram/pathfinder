from __future__ import annotations

from collections.abc import AsyncGenerator
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pathfinder.persistence.models import User
from pathfinder.platform.security import create_user_token

_AST = {
    "recordType": "transcript",
    "root": {
        "id": "root",
        "searchName": "GenesByTaxon",
        "parameters": {"organism": {"type": "string", "value": "Plasmodium"}},
    },
}


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


def _client_for(app: FastAPI, user_id: UUID) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    client.cookies.set("pathfinder-auth", create_user_token(user_id))
    return client


@pytest.fixture
async def api_client(
    app: FastAPI,
    patch_app_db_engine: None,
    seed_user: User,
) -> AsyncGenerator[httpx.AsyncClient]:
    del patch_app_db_engine
    async with _client_for(app, seed_user.id) as client:
        yield client


async def test_conversation_crud_lifecycle(api_client: httpx.AsyncClient) -> None:
    created = await api_client.post(
        "/api/v1/conversations",
        json={"name": "Kinase strategy", "siteId": "plasmodb", "strategyAst": _AST},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    conv_id = body["id"]
    UUID(conv_id)
    assert body["name"] == "Kinase strategy"
    assert body["siteId"] == "plasmodb"
    assert body["isSaved"] is False

    listed = await api_client.get(
        "/api/v1/conversations", params={"siteId": "plasmodb"}
    )
    assert listed.status_code == 200
    assert conv_id in [c["id"] for c in listed.json()]

    got = await api_client.get(f"/api/v1/conversations/{conv_id}")
    assert got.status_code == 200
    assert got.json()["name"] == "Kinase strategy"

    ast = await api_client.get(f"/api/v1/conversations/{conv_id}/ast")
    assert ast.status_code == 200
    assert ast.json()["root"]["searchName"] == "GenesByTaxon"

    patched = await api_client.patch(
        f"/api/v1/conversations/{conv_id}",
        json={"name": "Renamed kinases", "isSaved": True},
    )
    assert patched.status_code == 200
    patched_body = patched.json()
    assert patched_body["name"] == "Renamed kinases"
    assert patched_body["isSaved"] is True

    deleted = await api_client.delete(f"/api/v1/conversations/{conv_id}")
    assert deleted.status_code == 204

    after = await api_client.get("/api/v1/conversations", params={"siteId": "plasmodb"})
    assert conv_id not in [c["id"] for c in after.json()]


async def test_other_user_cannot_read_conversation(
    app: FastAPI,
    patch_app_db_engine: None,
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    del patch_app_db_engine
    created = await api_client.post(
        "/api/v1/conversations",
        json={"name": "Private", "siteId": "plasmodb", "strategyAst": _AST},
    )
    conv_id = created.json()["id"]

    other = User(id=uuid4())
    db_session.add(other)
    await db_session.flush()
    await db_session.commit()

    async with _client_for(app, other.id) as intruder:
        resp = await intruder.get(f"/api/v1/conversations/{conv_id}")
    assert resp.status_code in (403, 404)
