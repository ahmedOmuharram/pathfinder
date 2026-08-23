from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import httpx
import pytest
from assistant_core.memory.schemas import MemoryValue
from assistant_core.memory.store import MemoryStore


@pytest.mark.asyncio
async def test_list_memories_grouped_by_namespace(
    authed_client: httpx.AsyncClient,
    authed_user_id: UUID,
    app_memory_store: MemoryStore,
) -> None:
    await app_memory_store.put(
        user_id=authed_user_id,
        value=MemoryValue(
            kind="gene_set",
            name="a",
            summary="b",
            tags=[],
            content={},
            created_at=datetime.now(UTC),
        ),
    )
    resp = await authed_client.get("/api/v1/memories")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["geneSets"]) == 1
    assert body["strategies"] == []


@pytest.mark.asyncio
async def test_delete_memory_writes_tombstone(
    authed_client: httpx.AsyncClient,
    authed_user_id: UUID,
    app_memory_store: MemoryStore,
) -> None:
    value = MemoryValue(
        kind="knowledge",
        name="t",
        summary="u",
        tags=[],
        content={"fact": "x"},
        created_at=datetime.now(UTC),
    )
    key = await app_memory_store.put(user_id=authed_user_id, value=value)
    resp = await authed_client.delete(f"/api/v1/memories/{key}?kind=knowledge")
    assert resp.status_code == 204
    remaining = await app_memory_store.list_all(
        user_id=authed_user_id, kind="knowledge"
    )
    assert remaining == []


@pytest.mark.asyncio
async def test_search_returns_relevant(
    authed_client: httpx.AsyncClient,
    authed_user_id: UUID,
    app_memory_store: MemoryStore,
) -> None:
    for summary in ["plasmodium drug targets", "cookie recipe"]:
        await app_memory_store.put(
            user_id=authed_user_id,
            value=MemoryValue(
                kind="knowledge",
                name=summary[:10],
                summary=summary,
                tags=[],
                content={},
                created_at=datetime.now(UTC),
            ),
        )
    resp = await authed_client.get("/api/v1/memories/search?q=antimalarial%20drugs")
    assert resp.status_code == 200
    hits = resp.json()["hits"]
    assert hits
    assert "plasmodium" in hits[0]["value"]["summary"]


@pytest.mark.asyncio
async def test_patch_memory_updates_fields(
    authed_client: httpx.AsyncClient,
    authed_user_id: UUID,
    app_memory_store: MemoryStore,
) -> None:
    value = MemoryValue(
        kind="knowledge",
        name="old_name",
        summary="s",
        tags=["one"],
        content={},
        created_at=datetime.now(UTC),
    )
    key = await app_memory_store.put(user_id=authed_user_id, value=value)
    resp = await authed_client.patch(
        f"/api/v1/memories/{key}?kind=knowledge",
        json={"name": "new_name", "tags": ["two"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["value"]["name"] == "new_name"
    assert body["value"]["tags"] == ["two"]
