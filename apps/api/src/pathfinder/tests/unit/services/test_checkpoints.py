from __future__ import annotations

import os
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import TypedDict
from uuid import uuid4

import psycopg
import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy import text

from pathfinder.ai.chat.checkpointer import to_psycopg_url
from pathfinder.persistence.models import User
from pathfinder.persistence.repositories.checkpoint_label import (
    CheckpointLabelRepository,
)
from pathfinder.persistence.session import async_session_factory
from pathfinder.services.checkpoints import (
    CheckpointNode,
    CheckpointService,
    CheckpointSnapshot,
)


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
class _Seed:
    thread_id: str
    leaf_cp: str
    mid_cp: str
    root_cp: str
    graph_factory: Callable[
        [], CompiledStateGraph[_CounterState, None, _CounterState, _CounterState]
    ]


@pytest.fixture
async def checkpoint_saver(
    db_cleaner: None, patch_app_db_engine: None
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
async def checkpoint_seed(
    checkpoint_saver: AsyncPostgresSaver,
) -> _Seed:
    thread_id = str(uuid4())
    graph = _build_test_graph(checkpoint_saver)
    config = {"configurable": {"thread_id": thread_id}}
    await graph.ainvoke(
        {"counter": 0, "history": [], "user_prompt": "first"},
        config=config,
    )

    psycopg_url = to_psycopg_url(os.environ["DATABASE_URL"])
    async with await psycopg.AsyncConnection.connect(
        psycopg_url, autocommit=True
    ) as conn, conn.cursor() as cursor:
        await cursor.execute(
            "SELECT checkpoint_id, parent_checkpoint_id, "
            "(metadata->>'step')::int AS step "
            "FROM checkpoints WHERE thread_id = %s AND checkpoint_ns = '' "
            "ORDER BY (metadata->>'step')::int ASC NULLS LAST",
            (thread_id,),
        )
        rows = await cursor.fetchall()
    assert len(rows) >= 3, f"expected at least 3 checkpoints, got {len(rows)}"
    root_cp = rows[0][0]
    mid_cp = rows[len(rows) // 2][0]
    leaf_cp = rows[-1][0]

    def _factory() -> (
        CompiledStateGraph[_CounterState, None, _CounterState, _CounterState]
    ):
        return _build_test_graph(checkpoint_saver)

    return _Seed(
        thread_id=thread_id,
        root_cp=root_cp,
        mid_cp=mid_cp,
        leaf_cp=leaf_cp,
        graph_factory=_factory,
    )


@pytest.mark.asyncio
async def test_list_tree_returns_nodes_in_step_order(
    checkpoint_seed: _Seed,
) -> None:
    svc = CheckpointService(
        session_factory=async_session_factory,
        graph_factory=checkpoint_seed.graph_factory,
    )
    nodes = await svc.list_tree(thread_id=checkpoint_seed.thread_id)
    assert all(isinstance(n, CheckpointNode) for n in nodes)
    assert len(nodes) >= 3
    # Steps must be non-decreasing.
    steps = [n.step for n in nodes]
    assert steps == sorted(steps)
    # Exactly one root (no parent) per thread.
    roots = [n for n in nodes if n.parent_checkpoint_id is None]
    assert len(roots) == 1


@pytest.mark.asyncio
async def test_list_tree_node_names_derived_from_branch_writes(
    checkpoint_seed: _Seed,
) -> None:
    """Each non-root checkpoint should know which node just produced it.

    The service derives the node name from the parent checkpoint's
    ``branch:to:<node>`` channel write — that is LangGraph's own routing
    mechanism, so it is the authoritative source.
    """
    svc = CheckpointService(
        session_factory=async_session_factory,
        graph_factory=checkpoint_seed.graph_factory,
    )
    nodes = await svc.list_tree(thread_id=checkpoint_seed.thread_id)
    by_step = {n.step: n for n in nodes}
    # step 0 follows step -1; the route key was branch:to:bump.
    assert by_step[0].node == "bump"
    # step 1 follows step 0; the route key was branch:to:finish.
    assert by_step[1].node == "finish"


@pytest.mark.asyncio
async def test_list_tree_includes_user_labels_when_user_id_supplied(
    checkpoint_seed: _Seed,
) -> None:
    user_id = uuid4()
    async with async_session_factory() as session:
        session.add(User(id=user_id))
        await session.commit()

    repo = CheckpointLabelRepository(session_factory=async_session_factory)
    await repo.set_label(
        thread_id=checkpoint_seed.thread_id,
        checkpoint_id=checkpoint_seed.leaf_cp,
        user_id=user_id,
        label="my favourite",
        pinned=True,
    )

    svc = CheckpointService(
        session_factory=async_session_factory,
        graph_factory=checkpoint_seed.graph_factory,
    )
    nodes = await svc.list_tree(
        thread_id=checkpoint_seed.thread_id, user_id=user_id
    )
    leaf = next(n for n in nodes if n.checkpoint_id == checkpoint_seed.leaf_cp)
    assert leaf.label == "my favourite"
    assert leaf.pinned is True
    # Other nodes should have no label.
    others = [n for n in nodes if n.checkpoint_id != checkpoint_seed.leaf_cp]
    assert all(o.label is None and o.pinned is False for o in others)


@pytest.mark.asyncio
async def test_get_snapshot_returns_typed_state(
    checkpoint_seed: _Seed,
) -> None:
    svc = CheckpointService(
        session_factory=async_session_factory,
        graph_factory=checkpoint_seed.graph_factory,
    )
    snap = await svc.get_snapshot(
        thread_id=checkpoint_seed.thread_id,
        checkpoint_id=checkpoint_seed.leaf_cp,
    )
    assert isinstance(snap, CheckpointSnapshot)
    assert snap.checkpoint_id == checkpoint_seed.leaf_cp
    assert snap.thread_id == checkpoint_seed.thread_id
    assert "history" in snap.values
    assert snap.values.get("counter") == 1


@pytest.mark.asyncio
async def test_fork_creates_branched_checkpoint_with_correct_parent(
    checkpoint_seed: _Seed,
) -> None:
    svc = CheckpointService(
        session_factory=async_session_factory,
        graph_factory=checkpoint_seed.graph_factory,
    )
    new_cp = await svc.fork(
        thread_id=checkpoint_seed.thread_id,
        from_checkpoint_id=checkpoint_seed.mid_cp,
        state_override={"user_prompt": "forked prompt"},
        as_node=None,
    )
    assert new_cp != checkpoint_seed.mid_cp
    tree = await svc.list_tree(thread_id=checkpoint_seed.thread_id)
    forked = next((n for n in tree if n.checkpoint_id == new_cp), None)
    assert forked is not None
    assert forked.parent_checkpoint_id == checkpoint_seed.mid_cp


@pytest.mark.asyncio
async def test_fork_with_empty_override_still_creates_new_checkpoint(
    checkpoint_seed: _Seed,
) -> None:
    svc = CheckpointService(
        session_factory=async_session_factory,
        graph_factory=checkpoint_seed.graph_factory,
    )
    new_cp = await svc.fork(
        thread_id=checkpoint_seed.thread_id,
        from_checkpoint_id=checkpoint_seed.leaf_cp,
        state_override=None,
        as_node=None,
    )
    assert new_cp != checkpoint_seed.leaf_cp
    snap = await svc.get_snapshot(
        thread_id=checkpoint_seed.thread_id, checkpoint_id=new_cp
    )
    assert snap.parent_checkpoint_id == checkpoint_seed.leaf_cp


@pytest.mark.asyncio
async def test_checkpoint_node_camel_serialization() -> None:
    node = CheckpointNode(
        checkpoint_id="cp-1",
        parent_checkpoint_id="cp-0",
        thread_id="t1",
        source="loop",
        step=2,
        node="bump",
        created_at="2026-04-15T00:00:00+00:00",
        label=None,
        pinned=False,
    )
    dumped = node.model_dump(by_alias=True)
    assert dumped["checkpointId"] == "cp-1"
    assert dumped["parentCheckpointId"] == "cp-0"
    assert dumped["threadId"] == "t1"
    assert dumped["createdAt"] == "2026-04-15T00:00:00+00:00"
