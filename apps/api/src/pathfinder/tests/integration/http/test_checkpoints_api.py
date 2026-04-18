from __future__ import annotations

import os
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import TypedDict
from uuid import UUID, uuid4

import httpx
import psycopg
import pytest
from fastapi import FastAPI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy import text

from pathfinder.ai.conversation.checkpointer import to_psycopg_url
from pathfinder.persistence.models import Conversation, User
from pathfinder.persistence.repositories.checkpoint_label import (
    CheckpointLabelRepository,
)
from pathfinder.persistence.session import async_session_factory
from pathfinder.platform.security import create_user_token


class _CounterState(TypedDict, total=False):
    counter: int
    history: list[str]
    user_prompt: str


def _bump_counter(state: _CounterState) -> _CounterState:
    return {
        "counter": state.get("counter", 0) + 1,
        "history": [*state.get("history", []), "bumped"],
    }


def _finish(state: _CounterState) -> _CounterState:
    return {"history": [*state.get("history", []), "finished"]}


def _build_test_graph(
    checkpointer: AsyncPostgresSaver,
) -> CompiledStateGraph[_CounterState, None, _CounterState, _CounterState]:
    graph: StateGraph[_CounterState, None, _CounterState, _CounterState] = (
        StateGraph(_CounterState)
    )
    graph.add_node("bump", _bump_counter)
    graph.add_node("finish", _finish)
    graph.add_edge(START, "bump")
    graph.add_edge("bump", "finish")
    graph.add_edge("finish", END)
    return graph.compile(checkpointer=checkpointer)


@dataclass(frozen=True)
class _SeededChat:
    id: UUID
    leaf_cp: str
    mid_cp: str
    root_cp: str
    graph_factory: Callable[
        [], CompiledStateGraph[_CounterState, None, _CounterState, _CounterState]
    ]


@pytest.fixture
async def graph_saver(
    db_cleaner: None,
    patch_app_db_engine: None,
) -> AsyncIterator[AsyncPostgresSaver]:
    del db_cleaner, patch_app_db_engine
    psycopg_url = to_psycopg_url(os.environ["DATABASE_URL"])
    async with AsyncPostgresSaver.from_conn_string(psycopg_url) as saver:
        await saver.setup()
        async with async_session_factory() as session:
            await session.execute(
                text(
                    "TRUNCATE TABLE checkpoint_writes, checkpoint_blobs, "
                    "checkpoints RESTART IDENTITY CASCADE"
                )
            )
            await session.commit()
        yield saver


@pytest.fixture
async def app_with_graph(
    app: FastAPI,
    graph_saver: AsyncPostgresSaver,
) -> FastAPI:
    app.state.compiled_graph = _build_test_graph(graph_saver)
    return app


@pytest.fixture
async def seeded_chat(
    app_with_graph: FastAPI,
    authed_user_id: UUID,
    graph_saver: AsyncPostgresSaver,
) -> _SeededChat:
    del app_with_graph
    conversation_id = uuid4()
    async with async_session_factory() as session:
        session.add(
            Conversation(id=conversation_id, user_id=authed_user_id, site_id="plasmodb", name="")
        )
        await session.commit()

    graph = _build_test_graph(graph_saver)
    config = {"configurable": {"thread_id": str(conversation_id)}}
    await graph.ainvoke(
        {"counter": 0, "history": [], "user_prompt": "first"}, config=config
    )

    psycopg_url = to_psycopg_url(os.environ["DATABASE_URL"])
    async with await psycopg.AsyncConnection.connect(
        psycopg_url, autocommit=True
    ) as conn, conn.cursor() as cursor:
        await cursor.execute(
            "SELECT checkpoint_id FROM checkpoints "
            "WHERE thread_id = %s AND checkpoint_ns = '' "
            "ORDER BY (metadata->>'step')::int ASC",
            (str(conversation_id),),
        )
        rows = await cursor.fetchall()
    assert len(rows) >= 3
    root_cp = rows[0][0]
    mid_cp = rows[len(rows) // 2][0]
    leaf_cp = rows[-1][0]

    def _factory() -> (
        CompiledStateGraph[_CounterState, None, _CounterState, _CounterState]
    ):
        return graph

    return _SeededChat(
        id=conversation_id,
        root_cp=root_cp,
        mid_cp=mid_cp,
        leaf_cp=leaf_cp,
        graph_factory=_factory,
    )


@pytest.fixture
async def authed_app_client(
    app_with_graph: FastAPI,
    authed_user_id: UUID,
) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app_with_graph)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"X-Requested-With": "XMLHttpRequest"},
    ) as c:
        c.cookies.set("pathfinder-auth", create_user_token(authed_user_id))
        yield c


@pytest.mark.asyncio
async def test_list_checkpoints_returns_tree(
    authed_app_client: httpx.AsyncClient,
    seeded_chat: _SeededChat,
) -> None:
    resp = await authed_app_client.get(
        f"/api/v1/conversations/{seeded_chat.id}/checkpoints"
    )
    assert resp.status_code == 200
    nodes = resp.json()
    assert isinstance(nodes, list)
    assert len(nodes) >= 3
    sample = nodes[0]
    assert "checkpointId" in sample
    assert "parentCheckpointId" in sample
    assert "step" in sample
    assert "source" in sample


@pytest.mark.asyncio
async def test_list_checkpoints_returns_user_labels(
    authed_app_client: httpx.AsyncClient,
    seeded_chat: _SeededChat,
    authed_user_id: UUID,
) -> None:
    repo = CheckpointLabelRepository(session_factory=async_session_factory)
    await repo.set_label(
        thread_id=str(seeded_chat.id),
        checkpoint_id=seeded_chat.leaf_cp,
        user_id=authed_user_id,
        label="hello",
        pinned=True,
    )
    resp = await authed_app_client.get(
        f"/api/v1/conversations/{seeded_chat.id}/checkpoints"
    )
    assert resp.status_code == 200
    nodes = resp.json()
    leaf = next(n for n in nodes if n["checkpointId"] == seeded_chat.leaf_cp)
    assert leaf["label"] == "hello"
    assert leaf["pinned"] is True


@pytest.mark.asyncio
async def test_get_single_checkpoint(
    authed_app_client: httpx.AsyncClient,
    seeded_chat: _SeededChat,
) -> None:
    resp = await authed_app_client.get(
        f"/api/v1/conversations/{seeded_chat.id}/checkpoints/{seeded_chat.leaf_cp}"
    )
    assert resp.status_code == 200
    snap = resp.json()
    assert "values" in snap
    assert "next" in snap
    assert "metadata" in snap
    assert snap["checkpointId"] == seeded_chat.leaf_cp


@pytest.mark.asyncio
async def test_get_unknown_checkpoint_404(
    authed_app_client: httpx.AsyncClient,
    seeded_chat: _SeededChat,
) -> None:
    resp = await authed_app_client.get(
        f"/api/v1/conversations/{seeded_chat.id}/checkpoints/does-not-exist"
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_fork_endpoint_creates_branch(
    authed_app_client: httpx.AsyncClient,
    seeded_chat: _SeededChat,
) -> None:
    resp = await authed_app_client.post(
        f"/api/v1/conversations/{seeded_chat.id}/fork",
        json={
            "fromCheckpointId": seeded_chat.mid_cp,
            "stateOverride": {"user_prompt": "forked"},
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "newCheckpointId" in body
    new_cp = body["newCheckpointId"]
    assert new_cp != seeded_chat.mid_cp

    tree_resp = await authed_app_client.get(
        f"/api/v1/conversations/{seeded_chat.id}/checkpoints"
    )
    assert tree_resp.status_code == 200
    forked = next(
        (n for n in tree_resp.json() if n["checkpointId"] == new_cp), None
    )
    assert forked is not None
    assert forked["parentCheckpointId"] == seeded_chat.mid_cp


@pytest.mark.asyncio
async def test_label_lifecycle(
    authed_app_client: httpx.AsyncClient,
    seeded_chat: _SeededChat,
) -> None:
    # PUT a label.
    put_resp = await authed_app_client.put(
        f"/api/v1/conversations/{seeded_chat.id}/labels/{seeded_chat.leaf_cp}",
        json={"label": "draft 2", "pinned": True},
    )
    assert put_resp.status_code == 200
    body = put_resp.json()
    assert body["label"] == "draft 2"
    assert body["pinned"] is True
    assert body["checkpointId"] == seeded_chat.leaf_cp

    # GET lists it back.
    list_resp = await authed_app_client.get(
        f"/api/v1/conversations/{seeded_chat.id}/labels"
    )
    assert list_resp.status_code == 200
    labels = list_resp.json()
    assert any(l_["label"] == "draft 2" for l_ in labels)

    # PUT again to update.
    update_resp = await authed_app_client.put(
        f"/api/v1/conversations/{seeded_chat.id}/labels/{seeded_chat.leaf_cp}",
        json={"label": "draft 3", "pinned": False},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["label"] == "draft 3"

    # DELETE removes it.
    del_resp = await authed_app_client.delete(
        f"/api/v1/conversations/{seeded_chat.id}/labels/{seeded_chat.leaf_cp}"
    )
    assert del_resp.status_code == 204
    list_resp_2 = await authed_app_client.get(
        f"/api/v1/conversations/{seeded_chat.id}/labels"
    )
    assert list_resp_2.json() == []


@pytest.mark.asyncio
async def test_labels_are_user_scoped(
    authed_app_client: httpx.AsyncClient,
    seeded_chat: _SeededChat,
    authed_user_id: UUID,
) -> None:
    """Another user's label on the same checkpoint must not leak."""
    del authed_user_id
    other_user_id = uuid4()
    async with async_session_factory() as session:
        session.add(User(id=other_user_id))
        await session.commit()

    repo = CheckpointLabelRepository(session_factory=async_session_factory)
    await repo.set_label(
        thread_id=str(seeded_chat.id),
        checkpoint_id=seeded_chat.leaf_cp,
        user_id=other_user_id,
        label="other user label",
        pinned=False,
    )

    resp = await authed_app_client.get(
        f"/api/v1/conversations/{seeded_chat.id}/labels"
    )
    assert resp.status_code == 200
    assert resp.json() == []
